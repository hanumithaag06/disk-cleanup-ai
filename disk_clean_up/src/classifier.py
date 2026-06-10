# src/classifier.py

from ollama import chat
import json
from batch_processor import create_batches
from config import (
    CACHE_REANALYSIS_DAYS,
    BATCH_SIZE
)
from cache_manager import (
    get_cached_result,
    update_cache,
    threshold_changed,
    set_cached_threshold
)

def classify_files(files, threshold_days=180):

    files_for_llm = []

    final_results = []

    # ── Pull out duplicates — already decided, skip LLM ──
    duplicates     = [f for f in files if f.get("is_duplicate")]
    non_duplicates = [f for f in files if not f.get("is_duplicate")]

    # Duplicates go straight to final results
    for d in duplicates:
        final_results.append(d)

    # Everything below operates only on non_duplicates
    force_reanalysis = threshold_changed(
        threshold_days
    )

    for file in non_duplicates:

        cached = get_cached_result(
            file["name"]
        )

        if (
            not force_reanalysis
            and cached
        ):

            old_days = cached.get(
                "days_since_last_access",
                0
            )

            current_days = file[
                "days_since_last_access"
            ]

            difference = abs(
                current_days - old_days
            )

            if (
                difference
                < CACHE_REANALYSIS_DAYS
            ):

                cached["days_since_last_access"] = (
                    current_days
                )

                cached["size_mb"] = (
                    file["size_mb"]
                )

                cached["created_date"] = (
                    file["created_date"]
                )

                cached["path"] = (
                    file["path"]
                )

                final_results.append(
                    cached
                )

                continue

        files_for_llm.append(file)

    if not files_for_llm:

        return final_results

    all_results = []

    batches = list(
        create_batches(
            files_for_llm,
            BATCH_SIZE
        )
    )

    total_batches = len(batches)

    for batch_index, batch in enumerate(
        batches,
        start=1
    ):

        print(
            f"Classifying batch "
            f"{batch_index}/{total_batches}"
        )

        classification_input = [
            {
                "name": file["name"],
                "category": file["category"],
                "extension": file["extension"],
                "days_since_last_access":
                    file["days_since_last_access"]
            }
            for file in batch
        ]

        prompt = f"""
    You are an intelligent disk cleanup agent.

    Your task is to classify files as:

    - SAFE_DELETE
    - KEEP

    Use:

    1. File name
    2. File category
    3. File extension
    4. Days since last access

    Decision Priority:

    1. Days since last access (MOST IMPORTANT)
    2. File category
    3. File name
    4. File extension

    Rules:

    - Files with days_since_last_access >= {threshold_days}
    should usually be SAFE_DELETE.

    - Files with days_since_last_access < {threshold_days}
    should usually be KEEP.

    - Only override the age rule when the file name and category
    strongly suggest the opposite.

    Category Guidance:

    temporary
    → strong SAFE_DELETE candidate

    generated_file
    → moderate SAFE_DELETE candidate

    archive
    → moderate SAFE_DELETE candidate

    document
    → moderate KEEP candidate

    user_document
    → strong KEEP candidate

    Examples:

    temp_123.tmp
    → temporary

    cache_dump.zip
    → temporary

    backup_2024.zip
    → archive

    project_notes.txt
    → user_document

    report.pdf
    → document
    Decision Hierarchy (MUST FOLLOW)

    Step 1:
    Evaluate days_since_last_access.

    If days_since_last_access < {threshold_days}
    the default decision is KEEP.

    If days_since_last_access >= {threshold_days}
    the default decision is SAFE_DELETE.

    Step 2:
    Use category, file name and extension only to
    adjust confidence and reasoning.

    Step 3:
    Only override the default decision when there is
    very strong evidence that the file should be treated differently.

    Examples:

    dump.zip
    days_since_last_access = 0
    → KEEP

    cache.tmp
    days_since_last_access = 15
    → KEEP

    log.log
    days_since_last_access = 90
    → KEEP

    temp.tmp
    days_since_last_access = 300
    → SAFE_DELETE

    notes.txt
    days_since_last_access = 500
    → SAFE_DELETE

    project_report.pdf
    days_since_last_access = 600
    → SAFE_DELETE

    cache_dump.zip
    days_since_last_access = 700
    → SAFE_DELETE
    IMPORTANT:
    Reason Validation Rules:

    - The reason must be consistent with the exact
    days_since_last_access value.

    - If days_since_last_access = 0,
    say "not accessed for 0 days"
    or "recently accessed".

    - If days_since_last_access = X,
    the reason must contain X exactly.

    - Never say:
    "recently accessed"
    "last 180 days"
    "last year"
    "old file"
    "very old file"

    unless the statement is mathematically true.

    - Do not describe time ranges.
    Use the exact day count provided.

    Examples:

    days_since_last_access = 43
    → "Cache file not accessed for 43 days."

    days_since_last_access = 538
    → "Generated file not accessed for 538 days."

    days_since_last_access = 0
    → "Archive file not accessed for 0 days."

    days_since_last_access = 799
    → "User document not accessed for 799 days."
    Additional Rule:

    If days_since_last_access >= {threshold_days * 3},
    the default decision should be SAFE_DELETE
    regardless of category.

    Only override this when the file name strongly
    suggests a critical personal document.
    The age rule should determine the decision in most cases.

    Category, file name and extension are secondary signals.
    - days_since_last_access is the primary factor.
    - Category and extension are supporting signals.
    - Never recommend SAFE_DELETE for a recently accessed file without a strong reason.
    - Never recommend KEEP for a very old file without a strong reason.
    - Use the exact days_since_last_access value provided.
    - Never estimate months or years.
    - Never round values.
    - Keep the reason under 15 words.
    - Confidence must be between 0.50 and 0.99.
    - Do not use 1.00 confidence.

    Example:

    {{
        "name": "temp_115.tmp",
        "decision": "SAFE_DELETE",
        "confidence": 0.95,
        "reason": "Temporary file not accessed for 103 days."
    }}

    Return ONLY valid JSON.

    Schema:

    [
        {{
            "name": "string",
            "decision": "SAFE_DELETE" | "KEEP",
            "confidence": 0.95,
            "reason": "short explanation"
        }}
    ]

    Files:

    {json.dumps(classification_input, indent=2)}
    """

        response = chat(
            model="qwen2.5:3b",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        raw_response = (
            response.message.content.strip()
        )
        raw_response = raw_response.replace(
            "```json",
            ""
        ).replace(
            "```",
            ""
        ).strip()

        try:

            result = json.loads(
                raw_response
            )

            for item in result:

                matching_file = next(
                    (
                        f
                        for f in files_for_llm
                        if f["name"]
                        == item["name"]
                    ),
                    None
                )

                if matching_file:

                    item["days_since_last_access"] = (
                        matching_file[
                            "days_since_last_access"
                        ]
                    )

                    item["size_mb"] = (
                        matching_file["size_mb"]
                    )

                    item["created_date"] = (
                        matching_file[
                            "created_date"
                        ]
                    )

                    item["path"] = (
                        matching_file["path"]
                    )

                    # SAFETY OVERRIDE
                    days = matching_file[
                        "days_since_last_access"
                    ]

                    if (
                        days < threshold_days
                        and item["decision"] == "SAFE_DELETE"
                    ):
                        item["decision"] = "KEEP"

                        item["confidence"] = min(
                            item["confidence"],
                            0.80
                        )
                    category = matching_file["category"]

                    force_delete = False

                    if category == "temporary":
                        force_delete = (
                            days >= threshold_days
                        )

                    elif category in (
                        "generated_file",
                        "archive"
                    ):
                        force_delete = (
                            days >= threshold_days * 2
                        )

                    elif category in (
                        "document",
                        "user_document"
                    ):
                        force_delete = (
                            days >= threshold_days * 3
                        )

                    if (
                        force_delete
                        and item["decision"] == "KEEP"
                    ):
                        item["decision"] = "SAFE_DELETE"

                        item["confidence"] = max(
                            item["confidence"],
                            0.90
                        )
                    item["reason"] = (
                        f"{category.replace('_', ' ').title()} "
                        f"not accessed for {days} days."
                    )
                    print(
                        f"[{item['decision']}] "
                        f"{item['name']} | "
                        f"{days} days | "
                        f"{item['confidence']:.2f} | "
                        f"{item['reason']}"
                    )
                    update_cache(
                        item["name"],
                        item.copy()
                    )
            all_results.extend(result)


        except json.JSONDecodeError:

            print(
                f"Batch {batch_index} failed"
            )

            print(raw_response)

            continue
    set_cached_threshold(
        threshold_days
    )
    final_results.extend(
        all_results
    )
    keep_count = sum(
        1 for item in final_results
        if item["decision"] == "KEEP"
    )

    delete_count = sum(
        1 for item in final_results
        if item["decision"] == "SAFE_DELETE"
    )

    recoverable_space = sum(
        item.get("size_mb", 0)
        for item in final_results
        if item["decision"] == "SAFE_DELETE"
    )
    print("\n=== SCAN SUMMARY ===")
    print(f"Scanned: {len(final_results)}")
    print(f"KEEP: {keep_count}")
    print(f"SAFE_DELETE: {delete_count}")
    print(
        f"Recoverable Space: "
        f"{recoverable_space:.2f} MB"
    )
    
    return final_results
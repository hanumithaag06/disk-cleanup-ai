# main.py
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from discord_bot import start_bot

def main():
    print("Starting Disk Cleanup Recommender...")
    start_bot()

if __name__ == "__main__":
    main()
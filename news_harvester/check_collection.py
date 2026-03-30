import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.vector_store import initialize_collection, list_objects

def check_collection():
    print("Checking collection architecture...")
    initialize_collection()
    
    print("Counting live entries (up to 100 limit)...")
    objs = list_objects(page_size=100)
    print(f"Total entries found: {len(objs)}")

if __name__ == "__main__":
    check_collection()

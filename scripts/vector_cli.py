import argparse
import sys
import os

# Wire up the import tree to parse the workspace package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import utils.vector_store as vs

def main():
    parser = argparse.ArgumentParser(description="Admin CLI for Google Cloud Vector Search")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-collections
    subparsers.add_parser("list-collections", help="List all Vector Search Collections in the GCP Region")
    
    # create-collection
    create_parser = subparsers.add_parser("create-collection", help="Idempotently create a Vector Search collection")
    create_parser.add_argument("--id", type=str, required=False, help="Collection ID override")

    # list-objects
    list_obj_parser = subparsers.add_parser("list-objects", help="List active documents inside the target collection")
    list_obj_parser.add_argument("--limit", type=int, default=10, help="Max entries to return")

    # delete-object
    del_parser = subparsers.add_parser("delete-object", help="Purge a specific document by its hash ID")
    del_parser.add_argument("--id", type=str, required=True, help="Hash/ID of the data object to drop")

    args = parser.parse_args()

    if args.command == "list-collections":
        cols = vs.list_collections()
        for c in cols:
            print(f"- {c.name}")
        if not cols:
            print("No collections located in this region.")

    elif args.command == "create-collection":
        vs.initialize_collection(args.id)

    elif args.command == "list-objects":
        print(f"Reading up to {args.limit} objects from the index...")
        objs = vs.list_objects(args.limit)
        for o in objs:
            print(f"- [{o.data_object_id}] {o.data_object.data.get('title', '')}")
        if not objs:
            print("No indexed objects found.")

    elif args.command == "delete-object":
        vs.delete_object(args.id)
        print(f"Object '{args.id}' successfully queued for deletion.")

if __name__ == "__main__":
    main()

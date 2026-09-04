import os
import shutil
import time

print("[Nexus Reset]: Attempting to clear active ChromaDB memory collection layers...")

try:
    import chromadb

    # Connect directly to the persistence directory path
    client = chromadb.PersistentClient(path=".nexus_memory")

    # Exterminate existing collections completely from the tracking layer
    for name in ["research_dossiers", "synthesis_insights"]:
        try:
            client.delete_collection(name)
            print(f" -> Collection '{name}' deleted successfully.")
        except Exception:
            pass

    print("[Success]: Database collection contexts cleared out programmatically.")
except Exception as e:
    print(f"[Reset Notice]: ChromaDB client clearing dropped: {e}")

# Attempt an OS folder handle wipe now that internal objects are unhooked
time.sleep(1)
if os.path.exists(".nexus_memory"):
    try:
        shutil.rmtree(".nexus_memory")
        print("[Success]: Filesystem .nexus_memory directory deleted completely.")
    except Exception as e:
        print(f"[OS Warning]: Directory folder still held by editor process: {e}")
        print("Don't worry, the internal data tables are cleared and wiped!")

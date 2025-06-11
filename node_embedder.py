from json import load
import psycopg
from openai import OpenAI
from pgvector.psycopg import register_vector
import os
import uuid
from dotenv import load_dotenv

load_dotenv()
import os
print(os.environ.get("PGPASSWORD"))

conn = psycopg.connect(
    dbname="pgvector-age",
    user=os.environ.get("PGUSER"),
    password=os.environ.get("PGPASSWORD"),
    host="localhost",
    port="5431"
)

cursor = conn.cursor()

# Load the AGE extension (only needed once per session if not already loaded)
cursor.execute("LOAD 'age';")
# Set the search path to include AGE
cursor.execute("SET search_path = ag_catalog, \"$user\", public;")
conn.commit()

def add_vector_embeddings():
    print("\nAdding vector embeddings...")
    cursor.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Commit the transaction so the extension is available
    conn.commit()
    
    # Register vector extension
    register_vector(conn)
    
    # Create tables for vector embeddings and progress tracking
    print("Creating document_vectors and embedding_progress tables...")
    try:
        # Main embeddings table
        query = """
            CREATE TABLE IF NOT EXISTS document_vectors (
                id TEXT PRIMARY KEY,
                node_name TEXT,
                node_label TEXT,
                embedding vector(1536),  -- OpenAI text-embedding-3-small dimensionality
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """
        cursor.execute(query)
        
        # Progress tracking table
        progress_query = """
            CREATE TABLE IF NOT EXISTS embedding_progress (
                id SERIAL PRIMARY KEY,
                session_id TEXT,
                node_id TEXT,
                node_label TEXT,
                status TEXT CHECK (status IN ('pending', 'completed', 'failed')),
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, node_id)
            );
        """
        cursor.execute(progress_query)
        
        # Index for faster lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_embedding_progress_session_status ON embedding_progress(session_id, status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_embedding_progress_node_id ON embedding_progress(node_id);")
        
        conn.commit()
        print("Tables created successfully")
    except Exception as e:
        print(f"Error creating tables: {str(e)}")
        return
    
    # Set up OpenAI client
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))  # Changed this line
    
    # Generate or resume session ID
    import time
    session_id = f"embedding_session_{int(time.time())}"
    print(f"Starting embedding session: {session_id}")
    
    # Check if we should resume a previous session
    cursor.execute("""
        SELECT session_id, COUNT(*) as total, 
               SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
               SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
        FROM embedding_progress 
        WHERE status != 'completed'
        GROUP BY session_id 
        ORDER BY MAX(created_at) DESC 
        LIMIT 1
    """)
    
    previous_session = cursor.fetchone()
    if previous_session:
        resume_session_id, total, completed, failed = previous_session
        print(f"Found incomplete session: {resume_session_id}")
        print(f"Progress: {completed}/{total} completed, {failed} failed")
        
        # Check environment variable or use interactive prompt
        force_resume = os.getenv('RESUME_SESSION', '').lower() in ['true', '1', 'yes', 'y']
        force_new = os.getenv('NEW_SESSION', '').lower() in ['true', '1', 'yes', 'y']
        
        if force_resume:
            session_id = resume_session_id
            print(f"Resuming session (RESUME_SESSION=true): {session_id}")
        elif force_new:
            print(f"Starting new session (NEW_SESSION=true): {session_id}")
        else:
            # Interactive prompt
            response = input("Resume previous session? (y/n): ").lower().strip()
            if response == 'y':
                session_id = resume_session_id
                print(f"Resuming session: {session_id}")
            else:
                print(f"Starting new session: {session_id}")
    else:
        print(f"No previous incomplete sessions found. Starting new session: {session_id}")
    
    # Get all nodes from the graph database
    print("Retrieving nodes from graph database...")
    try:
        # First, get all vertex label tables for the graph
        cursor.execute("""
            SELECT name, relation
            FROM ag_catalog.ag_label
            WHERE kind = 'v' AND name != '_ag_label_vertex'
            AND graph = (SELECT graphid FROM ag_catalog.ag_graph WHERE name = 'from_csv')
        """)
        vertex_labels = cursor.fetchall()
        
        if not vertex_labels:
            print("No vertex labels found in the graph")
            return
            
        print(f"Found {len(vertex_labels)} vertex label types")
        
        all_nodes = []
        
        # Query each vertex label table
        for label_name, table_relation in vertex_labels:
            try:
                # Now that we retrieved the label names, we can embed them
                cursor.execute(f"""
                    SELECT * FROM cypher('from_csv', $$
                        MATCH (v:{label_name})
                        RETURN v.id, v.name, labels(v)
                    $$) AS (v_id agtype, v_name agtype, v_labels agtype);
                """)
                label_nodes = cursor.fetchall()
                all_nodes.extend(label_nodes)
                print(f"Found {len(label_nodes)} nodes in {label_name}")
                
            except Exception as label_error:
                print(f"Error querying {label_name}: {str(label_error)}")
                continue
        
        nodes = all_nodes
        print(f"Total found {len(nodes)} nodes to embed")
        
    except Exception as e:
        print(f"Error retrieving nodes: {str(e)}")
        return
    
    # Initialize progress tracking for new session
    if session_id.startswith("embedding_session_"):
        print("Initializing progress tracking...")
        for node_id, node_name, node_label in nodes:
            if node_name and node_name.strip():
                try:
                    cursor.execute("""
                        INSERT INTO embedding_progress (session_id, node_id, node_label, status)
                        VALUES (%s, %s, %s, 'pending')
                        ON CONFLICT (session_id, node_id) DO NOTHING
                    """, (session_id, str(node_id), str(node_label)))
                except Exception as e:
                    print(f"Error tracking node {node_id}: {str(e)}")
        conn.commit()
        print("Progress tracking initialized")
    
    # Get nodes that still need processing
    cursor.execute("""
        SELECT ep.node_id, ep.node_label, ep.status
        FROM embedding_progress ep
        WHERE ep.session_id = %s AND ep.status IN ('pending', 'failed')
        ORDER BY ep.id
    """, (session_id,))
    
    pending_nodes = cursor.fetchall()
    print(f"Found {len(pending_nodes)} nodes to process")
    
    # Get the actual node data for pending nodes
    nodes_to_process = []
    for pending_node_id, pending_node_label, status in pending_nodes:
        # Find the node data from our original query
        for node_id, node_name, node_label in nodes:
            if str(node_id) == pending_node_id:
                nodes_to_process.append((node_id, node_name, node_label))
                break
    
    # Process nodes in batches to avoid overwhelming the API
    batch_size = 100
    embedded_count = 0
    
    # Get current progress
    cursor.execute("""
        SELECT COUNT(*) FROM embedding_progress 
        WHERE session_id = %s AND status = 'completed'
    """, (session_id,))
    already_completed = cursor.fetchone()[0]
    
    print(f"Already completed: {already_completed}")
    print(f"Remaining to process: {len(nodes_to_process)}")
    
    for i in range(0, len(nodes_to_process), batch_size):
        batch = nodes_to_process[i:i + batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(nodes_to_process) + batch_size - 1)//batch_size}...")
        
        for node_id, node_name, node_label in batch:
            try:
                # Skip if node_name is empty or None
                if not node_name or node_name.strip() == '':
                    # Mark as failed with reason
                    cursor.execute("""
                        UPDATE embedding_progress 
                        SET status = 'failed', error_message = 'Empty node name', updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = %s AND node_id = %s
                    """, (session_id, str(node_id)))
                    continue
                
                # Check if already embedded (in case of duplicate processing)
                cursor.execute("""
                    SELECT 1 FROM document_vectors WHERE id = %s
                """, (str(node_id),))
                
                if cursor.fetchone():
                    # Mark as completed
                    cursor.execute("""
                        UPDATE embedding_progress 
                        SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = %s AND node_id = %s
                    """, (session_id, str(node_id)))
                    embedded_count += 1
                    continue
                
                # Create text to embed (combine name and type for better context)
                text_to_embed = f"{node_label}: {node_name}"
                
                # Generate embedding using OpenAI
                response = openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text_to_embed
                )
                
                embedding = response.data[0].embedding
                
                # Insert into document_vectors table
                cursor.execute("""
                    INSERT INTO document_vectors (id, node_name, node_label, embedding)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        node_name = EXCLUDED.node_name,
                        node_label = EXCLUDED.node_label,
                        embedding = EXCLUDED.embedding
                """, (str(node_id), str(node_name), str(node_label), embedding))
                
                # Mark as completed in progress table
                cursor.execute("""
                    UPDATE embedding_progress 
                    SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = %s AND node_id = %s
                """, (session_id, str(node_id)))
                
                embedded_count += 1
                
                if embedded_count % 50 == 0:
                    total_completed = already_completed + embedded_count
                    print(f"  Embedded {embedded_count} in this session ({total_completed} total completed)...")
                    
            except Exception as e:
                error_msg = str(e)
                print(f"Error embedding node {node_id} ({node_name}): {error_msg}")
                
                # Mark as failed in progress table
                cursor.execute("""
                    UPDATE embedding_progress 
                    SET status = 'failed', error_message = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = %s AND node_id = %s
                """, (error_msg, session_id, str(node_id)))
                continue
        
        # Commit batch
        try:
            conn.commit()
            print(f"  Committed batch {i//batch_size + 1}")
        except Exception as e:
            print(f"Error committing batch: {str(e)}")
            conn.rollback()
    
    # Final progress report
    cursor.execute("""
        SELECT status, COUNT(*) 
        FROM embedding_progress 
        WHERE session_id = %s 
        GROUP BY status
    """, (session_id,))
    
    final_stats = dict(cursor.fetchall())
    total_final_completed = final_stats.get('completed', 0)
    total_failed = final_stats.get('failed', 0)
    total_pending = final_stats.get('pending', 0)
    
    print(f"\nSession {session_id} Summary:")
    print(f"Successfully embedded: {total_final_completed}")
    print(f"Failed: {total_failed}")
    print(f"Still pending: {total_pending}")
    print("Vector embeddings processing completed!")

def check_embedding_progress():
    """Check progress of all embedding sessions"""
    cursor.execute("""
        SELECT session_id, 
               COUNT(*) as total,
               SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
               SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
               SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
               MIN(created_at) as started_at,
               MAX(updated_at) as last_updated
        FROM embedding_progress 
        GROUP BY session_id 
        ORDER BY started_at DESC
    """)
    
    sessions = cursor.fetchall()
    
    if not sessions:
        print("No embedding sessions found.")
        return
    
    print("\nEmbedding Sessions Progress:")
    print("=" * 80)
    for session_id, total, completed, failed, pending, started_at, last_updated in sessions:
        completion_rate = (completed / total * 100) if total > 0 else 0
        print(f"Session: {session_id}")
        print(f"  Started: {started_at}")
        print(f"  Last Updated: {last_updated}")
        print(f"  Progress: {completed}/{total} ({completion_rate:.1f}%)")
        print(f"  Failed: {failed}, Pending: {pending}")
        print("-" * 40)

def cleanup_failed_nodes(session_id):
    """Reset failed nodes to pending status for retry"""
    cursor.execute("""
        UPDATE embedding_progress 
        SET status = 'pending', error_message = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE session_id = %s AND status = 'failed'
    """, (session_id,))
    
    updated_count = cursor.rowcount
    conn.commit()
    print(f"Reset {updated_count} failed nodes to pending status")

def get_failed_nodes_summary(session_id):
    """Get summary of failed nodes by error type"""
    cursor.execute("""
        SELECT error_message, COUNT(*) as count
        FROM embedding_progress 
        WHERE session_id = %s AND status = 'failed'
        GROUP BY error_message
        ORDER BY count DESC
    """, (session_id,))
    
    failures = cursor.fetchall()
    if failures:
        print(f"\nFailure summary for session {session_id}:")
        for error_msg, count in failures:
            print(f"  {error_msg}: {count} nodes")
    else:
        print(f"No failures found for session {session_id}")

# Main execution
import sys

try:
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "progress":
            check_embedding_progress()
        elif command == "retry" and len(sys.argv) > 2:
            session_id = sys.argv[2]
            cleanup_failed_nodes(session_id)
            print(f"Failed nodes reset for session {session_id}. Run without arguments to continue.")
        elif command == "failures" and len(sys.argv) > 2:
            session_id = sys.argv[2]
            get_failed_nodes_summary(session_id)
        else:
            print("Usage:")
            print("  python node_embedder.py                    # Start/resume embedding")
            print("  python node_embedder.py progress           # Check all sessions progress")
            print("  python node_embedder.py retry <session_id> # Reset failed nodes to retry")
            print("  python node_embedder.py failures <session_id> # Show failure summary")
    else:
        add_vector_embeddings()

except Exception as e:
    conn.rollback()
    print(f"Error: {str(e)}")
    print("Connection was rolled back")

finally:
    # Close the connection
    cursor.close()
    conn.close()
    print("\nDatabase connection closed.")
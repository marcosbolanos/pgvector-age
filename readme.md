# easy-graph-vectordb

This repo will quickly help you setup a graph + vector database using free and open-source Postgres extensions, inside Docker.

## GitHub LFS

**IMPORTANT : to clone this repo, make sure to have git-lfs installed on your system**

```#
sudo apt install git-lfs
git lfs install
```

You can then `git clone` the repo as usual. If you cloned the file without LFS installed, you can fix it by running `git lfs pull`.

## Pre-loading CSVs

Inside of /container/csv, you may optionally put your nodes and edges in Apache AGE's CSV format to quickly load that data. The file structure is as follows : 

- Each file corresponds to a diffrent node or edge type (called "label") 
- The node and edge labels that will be used correspond to the filenames (without .csv)

## Running the database

### Using Docker

Make sure you've set your `$OPENAI_API_KEY`, `$PGUSER` and `$PGPASSWORD` environment variables.

With docker installed on your system, you can copy-paste this into your terminal to install.

```
# Replace 5431 by the port you want
PORT=5431

# Create a volume for persistent storage
docker volume create db_volume

# Build the image from the Dockerfile
docker build -t pgvector-age ./container

# Run container with networking and persistence
docker run \
  --name pgvector-age -d \
  -p "$PORT":5432 \
  -e OPENAI_API_KEY \
  -e POSTGRES_USER=$PGUSER \
  -e POSTGRES_PASSWORD=$PGPASSWORD \
  -v db_volume:/var/lib/postgresql/data:Z \
  pgvector-age

# Quickly load the a graph from the CSVs
docker exec pgvector-age python3 csv_loader.py
```

### OpenAI embeddings

If you want to add embeddings to every single node in your database, you can do so by running the node_embedder.py script. It will be done from your machine, not from the container.

```
# Add openai embeddings to nodes 
python -m venv .venv
pip install -r requirements.txt
./venv/bin/python node_embedder.py
```
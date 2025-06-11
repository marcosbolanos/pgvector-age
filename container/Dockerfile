FROM postgres:16.9-bookworm

RUN apt-get update && \
    apt-get install -y \
        git \
        build-essential \
        postgresql-server-dev-16 \
        flex \
        bison \
        libxml2-dev \
        python3 \
        pip \
        && rm -rf /var/lib/apt/lists/*

# Clone and build Apache AGE
RUN git clone https://github.com/apache/age.git /age && \
    cd /age && \
    make && \
    make install 
    
# Clone and build PGVector
RUN cd /tmp && \
    git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git && \
    cd pgvector && \
    make && \
    make install 

# Enable AGE on container start
RUN echo "shared_preload_libraries='age'" >> /usr/share/postgresql/postgresql.conf.sample
# Configure PostgreSQL to load vector extension
RUN echo "shared_preload_libraries = 'vector'" >> /usr/share/postgresql/postgresql.conf.sample

# Set environment variables
ENV POSTGRES_DB=pgvector-age

# Copy initialization SQL (runs automatically at runtime)
COPY init.sql /docker-entrypoint-initdb.d/

# Copy every necessary file into the container
COPY csv_loader.py /
COPY requirements.txt /
COPY ./csv /csv

ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN pip install -r /requirements.txt


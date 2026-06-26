-- =============================================================================
-- Homepedia — Schéma PostgreSQL + PostGIS
-- Tables de dimension géographique (régions, départements, communes)
-- =============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS postgis;

-- =============================================================================
-- Tables de dimension (COG — Code Officiel Géographique)
-- =============================================================================

CREATE TABLE IF NOT EXISTS regions (
    code_region VARCHAR(3) PRIMARY KEY,
    nom VARCHAR(255) NOT NULL,
    geom GEOMETRY(MultiPolygon, 4326)
);

CREATE TABLE IF NOT EXISTS departements (
    code_departement VARCHAR(3) PRIMARY KEY,
    nom VARCHAR(255) NOT NULL,
    code_region VARCHAR(3) REFERENCES regions(code_region),
    geom GEOMETRY(MultiPolygon, 4326)
);

CREATE TABLE IF NOT EXISTS communes (
    code_commune VARCHAR(5) PRIMARY KEY,
    nom VARCHAR(255) NOT NULL,
    code_departement VARCHAR(3) REFERENCES departements(code_departement),
    code_region VARCHAR(3) REFERENCES regions(code_region),
    code_postal VARCHAR(5),
    population INTEGER,
    superficie FLOAT,
    densite FLOAT,
    latitude FLOAT,
    longitude FLOAT,
    geom GEOMETRY(MultiPolygon, 4326),
    geom_simplified GEOMETRY(MultiPolygon, 4326)
);

-- =============================================================================
-- Tables de faits — DVF (Demandes de Valeurs Foncières)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dvf_transactions (
    id SERIAL PRIMARY KEY,
    id_mutation VARCHAR(20),
    code_commune VARCHAR(5) REFERENCES communes(code_commune),
    date_mutation DATE,
    nature_mutation VARCHAR(30),
    type_local VARCHAR(50),
    valeur_fonciere FLOAT,
    surface_reelle_bati FLOAT,
    nb_pieces INTEGER,
    surface_terrain FLOAT,
    prix_m2 FLOAT,
    longitude FLOAT,
    latitude FLOAT,
    geom GEOMETRY(Point, 4326)
);

-- =============================================================================
-- Tables analytiques pré-calculées — Tendances prix
-- =============================================================================

CREATE TABLE IF NOT EXISTS price_trends (
    code_commune VARCHAR(5) REFERENCES communes(code_commune),
    annee INTEGER,
    trimestre INTEGER,
    type_local VARCHAR(50),
    prix_median_m2 FLOAT,
    nb_transactions INTEGER,
    variation_annuelle_pct FLOAT,
    PRIMARY KEY (code_commune, annee, trimestre, type_local)
);

-- =============================================================================
-- Tables de faits — DPE (Diagnostics de Performance Énergétique)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dpe_diagnostics (
    id SERIAL PRIMARY KEY,
    code_commune VARCHAR(5) REFERENCES communes(code_commune),
    date_diagnostic DATE,
    classe_energie CHAR(1),
    consommation_moyenne FLOAT,
    source VARCHAR(10)
);

-- =============================================================================
-- Cadastre — Parcelles cadastrales (contours Etalab)
-- =============================================================================

CREATE TABLE IF NOT EXISTS parcelles_cadastrales (
    id VARCHAR(20) PRIMARY KEY,
    code_commune VARCHAR(5) REFERENCES communes(code_commune),
    prefixe VARCHAR(3),
    section VARCHAR(2),
    numero VARCHAR(4),
    contenance INTEGER,
    created DATE,
    updated DATE,
    geom GEOMETRY(Polygon, 4326)
);

-- =============================================================================
-- IRIS — Quartiers infra-communaux (contours IGN)
-- =============================================================================

CREATE TABLE IF NOT EXISTS iris_quartiers (
    code_iris VARCHAR(9) PRIMARY KEY,          -- 5 chars commune + 4 chars IRIS
    code_commune VARCHAR(5) REFERENCES communes(code_commune),
    nom_iris VARCHAR(255),
    type_iris CHAR(1),                         -- H=habitat, A=activité, D=divers, Z=non découpé
    geom GEOMETRY(MultiPolygon, 4326)
);

-- =============================================================================
-- BPE — Équipements par commune (agrégation spark_bpe.py)
-- =============================================================================

CREATE TABLE IF NOT EXISTS bpe_commune_stats (
    code_commune      VARCHAR(5) PRIMARY KEY REFERENCES communes(code_commune),
    nb_equipements_total INTEGER,
    -- Grandes catégories (première lettre TYPEQU)
    nb_a              INTEGER,  -- Enseignement
    nb_b              INTEGER,  -- Sport / Culture
    nb_c              INTEGER,  -- Commerce
    nb_d              INTEGER,  -- Santé
    nb_e              INTEGER,  -- Transport
    nb_f              INTEGER,  -- Tourisme
    -- Types clés pour l'immobilier
    nb_maternelles    INTEGER,
    nb_primaires      INTEGER,
    nb_creches        INTEGER,
    nb_colleges       INTEGER,
    nb_lycees         INTEGER,
    nb_medecins       INTEGER,
    nb_pharmacies     INTEGER,
    nb_urgences       INTEGER,
    nb_supermarches   INTEGER,
    nb_hypermarches   INTEGER,
    nb_gares          INTEGER
);

-- =============================================================================
-- Sécurité — Délinquance communale (SSMSI)
-- =============================================================================

CREATE TABLE IF NOT EXISTS securite_commune (
    code_commune            VARCHAR(5) REFERENCES communes(code_commune),
    annee                   INTEGER,
    cambriolages_nombre     INTEGER,
    cambriolages_pour_mille NUMERIC(6,1),
    violences_nombre        INTEGER,
    violences_pour_mille    NUMERIC(6,1),
    vols_nombre             INTEGER,
    vols_pour_mille         NUMERIC(6,1),
    stups_nombre            INTEGER,
    stups_pour_mille        NUMERIC(6,1),
    destructions_nombre     INTEGER,
    destructions_pour_mille NUMERIC(6,1),
    PRIMARY KEY (code_commune, annee)
);

-- =============================================================================
-- Index
-- =============================================================================

-- B-tree (recherche textuelle, jointures)
CREATE INDEX IF NOT EXISTS idx_communes_nom ON communes (nom);
CREATE INDEX IF NOT EXISTS idx_communes_code_departement ON communes (code_departement);
CREATE INDEX IF NOT EXISTS idx_communes_code_region ON communes (code_region);
CREATE INDEX IF NOT EXISTS idx_communes_code_postal ON communes (code_postal);
CREATE INDEX IF NOT EXISTS idx_departements_code_region ON departements (code_region);

-- B-tree DPE
CREATE INDEX IF NOT EXISTS idx_dpe_code_commune ON dpe_diagnostics (code_commune);
CREATE INDEX IF NOT EXISTS idx_dpe_classe_energie ON dpe_diagnostics (classe_energie);
CREATE INDEX IF NOT EXISTS idx_dpe_date_diagnostic ON dpe_diagnostics (date_diagnostic);

-- B-tree DVF (filtres fréquents)
CREATE INDEX IF NOT EXISTS idx_dvf_code_commune ON dvf_transactions (code_commune);
CREATE INDEX IF NOT EXISTS idx_dvf_date_mutation ON dvf_transactions (date_mutation);
CREATE INDEX IF NOT EXISTS idx_dvf_type_local ON dvf_transactions (type_local);
CREATE INDEX IF NOT EXISTS idx_dvf_id_mutation ON dvf_transactions (id_mutation);

-- B-tree price_trends
CREATE INDEX IF NOT EXISTS idx_price_trends_commune ON price_trends (code_commune);

-- B-tree cadastre
CREATE INDEX IF NOT EXISTS idx_parcelles_code_commune ON parcelles_cadastrales (code_commune);
CREATE INDEX IF NOT EXISTS idx_parcelles_section ON parcelles_cadastrales (section);

-- B-tree IRIS
CREATE INDEX IF NOT EXISTS idx_iris_code_commune ON iris_quartiers (code_commune);
CREATE INDEX IF NOT EXISTS idx_iris_type ON iris_quartiers (type_iris);

-- GiST (requêtes spatiales PostGIS)
CREATE INDEX IF NOT EXISTS idx_regions_geom ON regions USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_departements_geom ON departements USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_communes_geom ON communes USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_communes_geom_simplified ON communes USING GIST (geom_simplified);
CREATE INDEX IF NOT EXISTS idx_dvf_geom ON dvf_transactions USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_parcelles_geom ON parcelles_cadastrales USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_iris_geom ON iris_quartiers USING GIST (geom);

-- Recherche par nom (tri-gram pour LIKE/ILIKE performant)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_communes_nom_trgm ON communes USING GIN (nom gin_trgm_ops);

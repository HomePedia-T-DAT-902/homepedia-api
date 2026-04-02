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
-- Index
-- =============================================================================

-- B-tree (recherche textuelle, jointures)
CREATE INDEX IF NOT EXISTS idx_communes_nom ON communes (nom);
CREATE INDEX IF NOT EXISTS idx_communes_code_departement ON communes (code_departement);
CREATE INDEX IF NOT EXISTS idx_communes_code_region ON communes (code_region);
CREATE INDEX IF NOT EXISTS idx_communes_code_postal ON communes (code_postal);
CREATE INDEX IF NOT EXISTS idx_departements_code_region ON departements (code_region);

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

-- GiST (requêtes spatiales PostGIS)
CREATE INDEX IF NOT EXISTS idx_regions_geom ON regions USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_departements_geom ON departements USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_communes_geom ON communes USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_communes_geom_simplified ON communes USING GIST (geom_simplified);
CREATE INDEX IF NOT EXISTS idx_dvf_geom ON dvf_transactions USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_parcelles_geom ON parcelles_cadastrales USING GIST (geom);

-- Recherche par nom (tri-gram pour LIKE/ILIKE performant)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_communes_nom_trgm ON communes USING GIN (nom gin_trgm_ops);

## Create DPP database from PHP version dump

### Search and replace

    openatlas_dpp with openatlas

### Created new database

    dropdb openatlas_dpp_origin
    createdb openatlas_dpp_origin -O openatlas
    psql openatlas_dpp_origin < dpp.sql

### Execute upgrades

    cd install/upgrade/
    psql openatlas_dpp_origin < 3.0.0.sql
    psql openatlas_dpp_origin < 3.2.0.sql


## Create Ostalpen database from original dump

### Add postgis extension to begin of Ostalpen SQL

    CREATE EXTENSION postgis;

### Search and replace following strings in Ostalpen SQL

    ; Owner: openatla

with

    ; Owner: openatlas

and

    openatla;
    openatla_wavemaker;
    openatla_watzingeralex;
    openatla_bergnermax;
    openatla_gutjahrchristoph;
    openatla_jansaviktor;

with

    openaltas;

### Create new database

    dropdb ostalpen
    createdb ostalpen -O openatlas

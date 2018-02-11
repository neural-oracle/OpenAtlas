## Create fresh database

    dropdb ostalpen
    createdb ostalpen -O openatlas

## Add postgis extension to begin of Ostalpen SQL

    CREATE EXTENSION postgis;

## Search and replace following strings in Ostalpen SQL

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

@echo off
rem ===========================================================================
rem  Moteur de recherche semantique multilingue -- lancement en un clic.
rem
rem  Ce script enchaine tout ce que le README demande de faire a la main :
rem
rem     1. cree l'environnement virtuel s'il n'existe pas
rem     2. installe les dependances si elles manquent
rem     3. telecharge le corpus arXiv s'il est absent
rem     4. construit les index FAISS et BM25 s'ils sont absents
rem     5. demarre l'API, attend qu'elle soit prete, demarre l'interface
rem
rem  Chaque etape deja faite est sautee. Le premier lancement prend de vingt
rem  minutes a une heure et demie (dependances + modele + encodage) ; les
rem  suivants prennent une vingtaine de secondes.
rem
rem  Le texte est volontairement sans accents : un fichier .bat accentue
rem  s'affiche en charabia des que la console n'est pas en UTF-8.
rem ===========================================================================

setlocal
title Moteur de recherche semantique
cd /d "%~dp0"

rem L'environnement virtuel est place HORS du dossier du projet, a dessein :
rem PyTorch et ses dependances pesent plusieurs Go, et un projet range dans
rem OneDrive verrait des milliers de fichiers inutiles partir en synchro.
set "VENV=%USERPROFILE%\.venvs\soso-stage"
set "PY=%VENV%\Scripts\python.exe"
set "PORT_API=8000"
set "PORT_UI=8501"

echo.
echo ======================================================================
echo    MOTEUR DE RECHERCHE SEMANTIQUE MULTILINGUE
echo ======================================================================
echo.

rem --- 1. Python est-il installe ? ---------------------------------------
where python >nul 2>&1
if errorlevel 1 goto err_python

rem --- 2. Environnement virtuel ------------------------------------------
if exist "%PY%" goto venv_deja
echo [1/5] Creation de l'environnement virtuel
echo       %VENV%
python -m venv "%VENV%"
if errorlevel 1 goto err_venv
goto venv_fait
:venv_deja
echo [1/5] Environnement virtuel .............. deja present
:venv_fait

rem --- 3. Dependances ----------------------------------------------------
"%PY%" -c "import faiss, sentence_transformers, fastapi, uvicorn, streamlit, rank_bm25, markdown" >nul 2>&1
if not errorlevel 1 goto deps_deja
echo [2/5] Installation des dependances : environ 2 Go a telecharger,
echo       comptez 5 a 15 minutes selon la connexion.
"%PY%" -m pip install --upgrade pip >nul 2>&1
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto err_pip
goto deps_faites
:deps_deja
echo [2/5] Dependances ........................ deja installees
:deps_faites

rem --- 4. Certificats SSL -------------------------------------------------
rem Beaucoup d'installations Python sous Windows n'ont aucun magasin de
rem certificats : la collecte arXiv echoue alors avec CERTIFICATE_VERIFY_FAILED
rem alors que le reseau fonctionne tres bien. On designe explicitement le
rem bundle certifi du venv, ce qui corrige le probleme sans jamais desactiver
rem la verification TLS.
rem Le chemin transite par un fichier temporaire plutot que par un for /f :
rem dans un for /f, cmd relance la commande via cmd /c et les guillemets
rem imbriques autour du chemin de python.exe se cassent silencieusement.
"%PY%" -c "import certifi;print(certifi.where())" > "%TEMP%\soso_certifi.txt" 2>nul
if not exist "%TEMP%\soso_certifi.txt" goto ssl_fait
set /p SSL_CERT_FILE=<"%TEMP%\soso_certifi.txt"
del "%TEMP%\soso_certifi.txt" >nul 2>&1
:ssl_fait

rem --- 5. Corpus arXiv ----------------------------------------------------
if not exist "data\brut\corpus_arxiv.jsonl" goto collecte
for %%A in ("data\brut\corpus_arxiv.jsonl") do if %%~zA GTR 1000 goto corpus_deja
:collecte
echo [3/5] Telechargement du corpus arXiv : environ 5 minutes.
echo       L'API arXiv impose 3 secondes entre deux appels, c'est normal.
"%PY%" scripts\1_collecter.py
if errorlevel 1 goto err_collecte
goto corpus_fait
:corpus_deja
echo [3/5] Corpus arXiv ....................... deja telecharge
:corpus_fait

rem --- 6. Index FAISS et BM25 --------------------------------------------
if exist "data\index\index.faiss" goto index_deja
echo [4/5] Construction des index : ETAPE LA PLUS LONGUE.
echo       Le modele est telecharge (470 Mo), puis chaque passage du corpus
echo       est encode. De 12 minutes a 1 heure selon le processeur.
echo       Cette etape n'est faite qu'une seule fois.
"%PY%" scripts\2_indexer.py
if errorlevel 1 goto err_index
goto index_fait
:index_deja
echo [4/5] Index FAISS et BM25 ................ deja construits
:index_fait

rem --- 7. Demarrage des deux serveurs -------------------------------------
echo [5/5] Demarrage des serveurs
start "API - moteur semantique" cmd /k ""%PY%" -m uvicorn api.main:application --host 127.0.0.1 --port %PORT_API%"

rem L'API charge l'index puis prechauffe le modele : une quinzaine de secondes
rem pendant lesquelles l'interface afficherait "API injoignable". On attend
rem donc qu'elle reponde avant d'ouvrir quoi que ce soit.
rem La sonde et les pauses passent par Python plutot que par curl et timeout :
rem ces deux commandes Windows sont masquees des que Git for Windows place ses
rem propres binaires en tete du PATH, ce qui est frequent. Python, lui, vient
rem d'etre verifie quelques lignes plus haut.
echo       Chargement de l'index et du modele en memoire...
set essais=0
:attente
"%PY%" -c "import urllib.request as u;u.urlopen('http://127.0.0.1:%PORT_API%/sante',timeout=2)" >nul 2>&1
if not errorlevel 1 goto api_prete
set /a essais+=1
if %essais% GTR 60 goto err_api
"%PY%" -c "import time;time.sleep(2)" >nul 2>&1
goto attente
:api_prete
echo       API prete sur http://127.0.0.1:%PORT_API%

rem L'interface est volontairement limitee a 127.0.0.1 : par defaut Streamlit
rem ecoute sur toutes les interfaces et devient visible depuis tout le reseau
rem local, ce qui n'a aucune raison d'etre pour une demo.
start "Interface - Streamlit" cmd /k ""%PY%" -m streamlit run ui/app.py --server.port %PORT_UI% --server.address 127.0.0.1 --server.headless true"
"%PY%" -c "import time;time.sleep(5)" >nul 2>&1
start "" "http://localhost:%PORT_UI%"

echo.
echo ======================================================================
echo    TOUT EST LANCE
echo ======================================================================
echo.
echo    Interface     http://localhost:%PORT_UI%
echo    API et docs   http://127.0.0.1:%PORT_API%/docs
echo.
echo    Deux fenetres se sont ouvertes, une par serveur. Pour arreter le
echo    projet : Ctrl+C dans chacune, ou fermez-les simplement.
echo.
echo    Cette fenetre-ci ne sert plus a rien, tu peux la fermer.
echo.
pause
exit /b 0

rem ===========================================================================
rem  Messages d'erreur : chacun dit quoi faire, pas seulement ce qui a rate.
rem ===========================================================================

:err_python
echo.
echo    ECHEC : Python est introuvable.
echo.
echo    Installe Python 3.10 ou plus recent depuis https://www.python.org
echo    en cochant "Add python.exe to PATH" pendant l'installation, puis
echo    relance ce script.
echo.
pause
exit /b 1

:err_venv
echo.
echo    ECHEC : impossible de creer l'environnement virtuel dans
echo    %VENV%
echo.
echo    Verifie que tu as les droits d'ecriture sur ce dossier.
echo.
pause
exit /b 1

:err_pip
echo.
echo    ECHEC : l'installation des dependances s'est interrompue.
echo.
echo    C'est presque toujours la connexion reseau. Relance simplement ce
echo    script : pip reprend ou il s'etait arrete.
echo.
pause
exit /b 1

:err_collecte
echo.
echo    ECHEC : le telechargement du corpus arXiv a echoue.
echo.
echo    Verifie ta connexion. Si le message parlait de CERTIFICATE_VERIFY_FAILED,
echo    ton Python n'a pas de magasin de certificats : ce script corrige
echo    normalement ce cas tout seul, a condition que le venv soit complet.
echo.
pause
exit /b 1

:err_index
echo.
echo    ECHEC : la construction des index s'est interrompue.
echo.
echo    Si le message parlait de memoire insuffisante, ouvre config.py et
echo    baisse TAILLE_LOT de 64 a 16, puis relance ce script.
echo.
pause
exit /b 1

:err_api
echo.
echo    ECHEC : l'API n'a pas repondu apres deux minutes.
echo.
echo    Regarde la fenetre intitulee "API - moteur semantique" : le message
echo    d'erreur s'y trouve. Cause frequente : le port %PORT_API% est deja
echo    occupe par un autre programme.
echo.
pause
exit /b 1

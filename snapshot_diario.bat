@echo off
cd /d "C:\Users\ferod\OneDrive\Desktop\Projeto-Cetel"
python -m core.sync.snapshot >> logs\snapshot.log 2>&1

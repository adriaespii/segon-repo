---
description: Update game, build executable and push to Git
---
This workflow ensures that every code change is accompanied by a fresh build and a clean Git repository.

1. Run PyInstaller to rebuild the executable:
// turbo
`pyinstaller WizardVsOgres_ULTIMATE_v2.4.spec --noconfirm`

2. Replace the main executable in the root directory:
// turbo
`move /Y "dist\WizardVsOgres_ULTIMATE_v2.4.exe" "WizardVsOgres.exe"`

3. Clean up the dist folder to avoid clutter:
// turbo
`del /Q "dist\*.exe"`

4. Stage all changes, including the new executable:
`git add .`

5. Commit with a descriptive message:
`git commit -m "Update game with latest features and build"`

6. Push to the master branch:
`git push origin master`

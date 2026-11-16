# Phase 9 release checklist

- [ ] Start from the latest `origin/main`.
- [ ] Run the complete Python test suite.
- [ ] Run JavaScript syntax checks for every `frontend/js/**/*.js` file.
- [ ] Compile Python modules and run `git diff --check`.
- [ ] Validate `wokwi_esp32_demo/diagram.json`.
- [ ] Verify `render.yaml` declares `HIMRAKSHAK_DEVICE_TOKENS` as an external secret.
- [ ] Verify the Pages workflow copies `index.html` and the complete `frontend/` tree.
- [ ] Confirm no credentials appear in static assets or tracked firmware.
- [ ] Verify local, standalone, and cloud read-only behavior.
- [ ] Check Render health and deployment commit in the Render dashboard.
- [ ] Check GitHub Pages workflow and published URL; a configured workflow alone
  is not evidence that Pages is live.
- [ ] Review the security findings and confirm no v2 radio/gateway/power scope
  was added.
- [ ] Confirm the branch is clean, pushed, and the PR targets `main`.

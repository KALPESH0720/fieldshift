# Crop Photograph Manifest & Missing Images Report (`docs/MISSING_CROP_IMAGES.md`)

- **Total crops in `src/data/crops.js`**: 60
- **Verified real photographs**: 60 (8 downloaded, 0 manual, 52 existing)
- **Missing real photographs**: 0
- **Purged synthetic/invalid/duplicate files**: 0

## How to Provide Manual Crop Photos (`data/manual-crop-photos/`)

If any crop cannot be fetched automatically, drop `<cropId>.jpg` or `<cropId>.png` (`>= 400px` on the short side, `> 8 KB`) into `data/manual-crop-photos/`, optionally add attribution in `data/manual-crop-photos/credits.json`, and run:

```bash
npm run crops:fetch
npm run crops:audit
```

All 60 crops in `src/data/crops.js` have verified, unique real photographs (`>= 3 KB` thumb, `>= 8 KB` card, `0` duplicates).

# Field Shift — Crop Image Audit Report (`docs/CROP_IMAGE_AUDIT.md`)

This document records the **Before Fix** and **After Fix** technical and visual audit of all 60 crops defined in `src/data/crops.js`.

## Summary Comparison (Before vs. After)

| Metric | Before Fix | After Fix |
| :--- | :---: | :---: |
| **Total Crops in `src/data/crops.js`** | 60 | 60 |
| **Verified Real Photographs (`>= 3 KB` thumb, `>= 8 KB` card, unique subject)** | 35 | **60** |
| **Thumbnails Under 3 KB (`< 3,072` bytes)** | 6 | **0** |
| **Duplicate Hash Groups (SHA-256 / Perceptual dHash)** | 1 group (`rice`, `paddy`) | **0 groups (0 crops)** |
| **Botanical Drawings / Wrong Subjects / Broken `/640px-` URLs** | 25 crops | **0 crops** |
| **Missing Files** | 0 | **0** |

---

## 1. Before-Fix Audit Findings (Root Causes Identified)

### 1.1 Why the Browser Still Showed Synthetic Emoji Tiles & Shared Bean Icons
1. **Service Worker Cache Trap (`vite.config.js` + Unversioned URLs)**: `vite.config.js` enabled the Workbox Service Worker in development (`devOptions: { enabled: true }`) with a catch-all `CacheFirst` rule (`cacheName: "image-cache"`, 30-day expiration) for `/\.(?:png|jpg|jpeg|svg|gif|webp|ico)$/i` and precached `crops/*-thumb.webp` without version query strings on `/crops/<id>-thumb.webp`. Any browser that had previously loaded the app continued serving the old `456–2,374` byte synthetic flat-green emoji WebP files from Service Worker CacheStorage (`image-cache` / `workbox-precache-v2`), where `beans`, `lentil`, `cowpea`, `chickpea`, `moong`, `pigeon-pea`, `soybean`, and `black-gram` shared the identical `🫘` bean icon tile.
2. **Mock Land Registry & Unmapped Plot Crops (`mockProviders.js` + `PlotList.jsx`)**: `mockProviders.js` assigned `landUse: "mixed agriculture" | "arable land"` and `cropDeclared: "Cereal" | "Vegetables" | "Tree crop"`. When rendered by `<CropImage />`, `getCrop()` fell back to `other` (`other-thumb.webp`) for every unmapped label, causing imported plots to display the same repeated image.
3. **Permissive `MIN_REAL_PHOTO_BYTES = 1500` in `scripts/fetch-crop-images.mjs`**: The previous pipeline accepted thumbnails down to `1,500` bytes, did not check for duplicate SHA-256/perceptual hashes, did not reject 19th-century botanical plates (`Köhler` / `Blanco`), and contained guessed Unsplash photo IDs that returned wrong subjects.

### 1.2 Duplicate Hash Groups (Before Fix)
- **`46f500a96b72ec25` (thumb) / `609dd9db0ec45b1a` (card)**: Shared identically by `rice` and `paddy` (both downloaded `https://images.unsplash.com/photo-1536304993881-ff6e9eefa2a6`, which depicted a bowl of cooked white restaurant rice).

### 1.3 Invalid Manifest Sources, Wrong Subjects & Under-3KB Thumbnails (Before Fix)
| Crop ID | Thumb Size (Before) | Card Size (Before) | Thumb SHA-256 | Root Issue (Before Fix) |
| :--- | :---: | :---: | :---: | :--- |
| `rice` | 3,794 B | 20,534 B | `46f500a96b7212c2` | Wrong subject (bowl of cooked white rice instead of paddy rice crop) + duplicate hash with paddy |
| `oats` | 7,164 B | 57,044 B | `5acfa3e350c0b8f2` | Wrong subject (Unsplash photo-1586201375761-83865001e31c shows white rice grains, not oats) |
| `lentil` | 8,836 B | 50,728 B | `cf62729b7950f5ad` | Manifest URL uses /640px- Wikimedia thumb (returns HTTP 400) |
| `pigeon-pea` | 3,762 B | 31,154 B | `446c0fe22fa2d97c` | Botanical illustration (Blanco 19th-century drawing, not a photograph) |
| `beans` | 4,042 B | 29,030 B | `b2d22664681c3e55` | Wrong subject (Unsplash photo-1551462147-ff29053bfc14 shows dry spaghetti pasta, not beans) |
| `peas` | 786 B | 6,576 B | `d65bbfdbf715d229` | Under 3 KB (786 B) + wrong subject (Unsplash photo-1587735243615-c03f25aaff15 shows an orange, not peas) |
| `mustard` | 5,324 B | 34,014 B | `9ecc9d5a1cd8988c` | Botanical illustration (Köhler Medizinal-Pflanzen drawing, not a photograph) |
| `sesame` | 6,036 B | 44,968 B | `6bd2a4de3eaaf66a` | Botanical illustration (Köhler Medizinal-Pflanzen drawing, not a photograph) |
| `rapeseed` | 2,734 B | 29,028 B | `f3cdc6ab5eecc710` | Under 3 KB (2,734 B) + wrong subject (Unsplash photo-1500382017468-9049fed747ef shows sunset landscape) |
| `cassava` | 5,230 B | 39,170 B | `395942d941e3beb9` | Botanical illustration (Köhler Medizinal-Pflanzen drawing, not a photograph) |
| `brinjal` | 1,468 B | 12,876 B | `24db916148d6a681` | Under 3 KB (1,468 B) + wrong subject (Unsplash photo-1615484477778-ca3b77940c25 shows a pear, not brinjal) |
| `okra` | 5,182 B | 36,274 B | `ed066a327095ff2e` | Manifest URL uses /640px- Wikimedia thumb (returns HTTP 400) |
| `cotton` | 3,324 B | 19,562 B | `9e021852e6dfb7f3` | Manifest URL uses /640px- Wikimedia thumb (returns HTTP 400) |
| `sugarcane` | 6,502 B | 56,836 B | `6e96cd2938b605a1` | Botanical illustration (Köhler Medizinal-Pflanzen drawing, not a photograph) |
| `tea` | 3,994 B | 22,436 B | `ef8091ea6f75c220` | Wrong subject (Unsplash photo-1564890369478-c89ca6d9cde9 shows ceramic teapot and cup, not tea crop) |
| `banana` | 1,428 B | 8,600 B | `0ff842849fca3468` | Under 3 KB (1,428 B, flat yellow background) |
| `mango` | 1,078 B | 7,634 B | `28771fa5c9ae8a49` | Under 3 KB (1,078 B, flat white background) |
| `citrus` | 2,410 B | 20,596 B | `fe714eaf36f9c3b5` | Under 3 KB (2,410 B, flat white background) |
| `cocoa` | 6,296 B | 52,214 B | `28f029ebfdd9d2ed` | Manifest URL uses /640px- Wikimedia thumb (returns HTTP 400) |
| `oil-palm` | 7,644 B | 1,04,912 B | `609470b815f5c9c8` | Botanical illustration (Köhler Medizinal-Pflanzen drawing, not a photograph) |
| `rubber` | 5,694 B | 45,588 B | `9d7a665df28824bc` | Botanical illustration (Köhler Medizinal-Pflanzen drawing, not a photograph) |
| `alfalfa` | 4,820 B | 42,166 B | `b27158302d4e145e` | Botanical illustration (19th-century botanical plate, not a photograph) |
| `black-gram` | 7,352 B | 67,124 B | `72cbd9b9422f1200` | Manifest URL uses /640px- Wikimedia thumb (returns HTTP 400) |
| `fenugreek` | 5,622 B | 51,176 B | `81b9351aff0f343b` | Botanical illustration (19th-century botanical plate, not a photograph) |
| `paddy` | 3,794 B | 20,534 B | `46f500a96b7212c2` | Wrong subject (bowl of cooked white rice) + duplicate hash with rice |

---

## 2. After-Fix Complete 60-Crop Audit Table

| Crop ID | Exists (Thumb / Card) | Thumb Bytes | Card Bytes | Thumb SHA-256 | Card SHA-256 | Perceptual dHash | Licence | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: |
| `rice` | Yes / Yes | 7,964 B | 46,050 B | `68e6cb1b57ee149b` | `859d5e957daeb6fa` | `9f2dadf8bdb471b7` | CC BY-SA 3.0 | Verified Real Photo |
| `wheat` | Yes / Yes | 8,802 B | 69,222 B | `eec7e74b86842324` | `c041cd6a84610408` | `6dd9db5a26664b49` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `maize` | Yes / Yes | 6,862 B | 50,604 B | `d66687bb8c4731ad` | `566b666dca0caddf` | `e418cea6572e2c17` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `sorghum` | Yes / Yes | 8,036 B | 93,734 B | `b1d4c895ccb03c1a` | `878c683c16693630` | `72b8c8ce4c686878` | CC BY-SA 3.0 | Verified Real Photo |
| `millet` | Yes / Yes | 8,194 B | 1,03,888 B | `c39ef0e7a6ed9bc6` | `c1f760d1eaef4f09` | `c8b6a99b8aa8e464` | Public domain | Verified Real Photo |
| `barley` | Yes / Yes | 5,034 B | 68,842 B | `2ac0791b1f184b55` | `0857a6bbcb8ff740` | `0d2d0da8a4564765` | CC BY 2.0 | Verified Real Photo |
| `oats` | Yes / Yes | 7,992 B | 49,074 B | `4c4883acf5841951` | `67bf7ebcd2d36bbf` | `ad195364291a28a8` | CC BY-SA 3.0 | Verified Real Photo |
| `chickpea` | Yes / Yes | 6,196 B | 38,278 B | `c033e187d9c043b9` | `0dbac9c43d23e5cb` | `0f0715383889b8b2` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `lentil` | Yes / Yes | 9,626 B | 71,244 B | `68ff577103722789` | `4ed8924bef2ad043` | `05c3c52362e3f26c` | CC BY-SA 2.5 | Verified Real Photo |
| `pigeon-pea` | Yes / Yes | 4,370 B | 23,064 B | `62fc9acbcda8d61c` | `f8c33e2eb345dc1c` | `729c9ca0cc4c3180` | Public domain | Verified Real Photo |
| `moong` | Yes / Yes | 4,028 B | 33,250 B | `1351fbfa51e701fd` | `962bf7ac1631fec9` | `2167d6b4b0c845ba` | CC BY-SA 4.0 | Verified Real Photo |
| `cowpea` | Yes / Yes | 7,976 B | 40,384 B | `d03864f34939976e` | `f67fb53eb97ea638` | `261331a924165a2a` | CC BY-SA 3.0 | Verified Real Photo |
| `soybean` | Yes / Yes | 4,298 B | 45,272 B | `2513a24df62d1e64` | `58d66aeaa4287cfa` | `37669a9b15ad9e17` | Public domain | Verified Real Photo |
| `beans` | Yes / Yes | 8,114 B | 86,518 B | `c10ccebc07e0d5e5` | `c12b56b1ef3d752f` | `a21b7a097957ba15` | CC BY-SA 3.0 | Verified Real Photo |
| `peas` | Yes / Yes | 5,410 B | 52,536 B | `790b1a17cd7d7197` | `eb24de86e5aef263` | `d25bb1321a54646c` | CC BY-SA 3.0 | Verified Real Photo |
| `groundnut` | Yes / Yes | 6,984 B | 42,644 B | `1bf293646416edef` | `88d001cca6965982` | `b32e2e6e495d595d` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `mustard` | Yes / Yes | 6,430 B | 41,400 B | `79b61506051869af` | `d132cb9f21fd22fa` | `b38f0763630ecee4` | CC BY-SA 4.0 | Verified Real Photo |
| `sunflower` | Yes / Yes | 6,198 B | 52,818 B | `b4fed333a6ec6ac2` | `e6b6f7f49f4f1911` | `79f0f0f0f0713427` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `sesame` | Yes / Yes | 4,610 B | 29,266 B | `803b91f5f3e26794` | `ff3d7b31531d9db1` | `2c6e8a981a18e966` | CC BY-SA 2.0 | Verified Real Photo |
| `rapeseed` | Yes / Yes | 9,070 B | 1,27,158 B | `ed01b25a9e38d480` | `7364d9582cede7f5` | `3701565525945353` | CC BY 3.0 | Verified Real Photo |
| `potato` | Yes / Yes | 3,856 B | 29,336 B | `96181a8726594df2` | `feb49ee9a6b57480` | `622129cd8d8b1a36` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `sweet-potato` | Yes / Yes | 4,880 B | 68,960 B | `357440c3b0941127` | `b2c79814edd6db95` | `82083c0340703c18` | CC BY-SA 3.0 | Verified Real Photo |
| `cassava` | Yes / Yes | 7,536 B | 83,102 B | `ffd21695cfb5fab3` | `709ad7a42edeb5fc` | `2b1a9456259c6fce` | CC BY-SA 4.0 | Verified Real Photo |
| `yam` | Yes / Yes | 3,598 B | 20,318 B | `8a4f3bb6042bf014` | `4e8785bfce4e1733` | `f296a664cccd4fcd` | CC BY-SA 4.0 | Verified Real Photo |
| `onion` | Yes / Yes | 6,758 B | 61,092 B | `5b3ba808874fd1f4` | `5486dcf5f7e1026e` | `a56d32a42d3d3525` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `garlic` | Yes / Yes | 5,840 B | 28,808 B | `ec9fe24e495fda4c` | `f7aef2f179ca70b6` | `5729b3265d191913` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `tomato` | Yes / Yes | 4,204 B | 50,240 B | `f0697997233d330a` | `b56f9387afd962c8` | `c4e6233311302008` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `brinjal` | Yes / Yes | 5,360 B | 43,032 B | `a859cc53ce98bf54` | `edfd25548a0dfe6a` | `2bcd991cb9fbcfcd` | CC BY 3.0 us | Verified Real Photo |
| `chilli` | Yes / Yes | 8,730 B | 66,720 B | `096c10c35d211553` | `142d3bf371fee7a6` | `5459da5e5292dad2` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `cabbage` | Yes / Yes | 7,424 B | 63,128 B | `f3d90910d9eca0b3` | `d1abaea5458d8268` | `59c98d6466cedccd` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `cauliflower` | Yes / Yes | 6,184 B | 36,974 B | `3ab356539e4c214b` | `7fcb58f4044d0d8b` | `4a963b1caca469a8` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `okra` | Yes / Yes | 5,640 B | 43,262 B | `d338e6ed018fc0d1` | `da1f824eac594e8b` | `3593d4a4ac6f66ac` | CC BY-SA 3.0 | Verified Real Photo |
| `cucumber` | Yes / Yes | 6,686 B | 61,078 B | `05d2df948dded5f6` | `f12e01be61487091` | `a3625a73d622c957` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `pumpkin` | Yes / Yes | 6,868 B | 44,734 B | `d9f69b35b540b750` | `c6f2dba48d4e6bee` | `1915272b863791d9` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `cotton` | Yes / Yes | 3,600 B | 23,632 B | `7ce6e095fcdfad8c` | `45f531c10eae7514` | `78e2c327c3d3ecec` | Public domain | Verified Real Photo |
| `sugarcane` | Yes / Yes | 7,564 B | 64,150 B | `83f4aeefe59eb107` | `ac968e1f68950823` | `535273736222b333` | CC BY 3.0 us | Verified Real Photo |
| `jute` | Yes / Yes | 4,134 B | 77,932 B | `069d6d8a0ae4468b` | `d3f0594c2670c8ca` | `0b0f1731312b8e6f` | CC BY 3.0 | Verified Real Photo |
| `tea` | Yes / Yes | 8,084 B | 83,868 B | `6f39e5a99d560902` | `5090eef927f425e5` | `35e5595db58fdbd6` | Public domain | Verified Real Photo |
| `coffee` | Yes / Yes | 8,792 B | 70,738 B | `f84dc1d07cbf315c` | `8744885914c38aa0` | `2624ad9d856e3999` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `tobacco` | Yes / Yes | 5,256 B | 42,086 B | `dd5635c30ad56166` | `0cfe9647da7661f6` | `48c8282442103313` | CC BY 2.5 | Verified Real Photo |
| `coconut` | Yes / Yes | 5,178 B | 53,998 B | `f040bb84c0610ea5` | `0d1e67a0f3fa73ff` | `236079d8dd352291` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `cashew` | Yes / Yes | 4,096 B | 25,590 B | `1b332989fa8d7344` | `ec7cffe731c1ca81` | `9387aecb4b2296b6` | CC BY-SA 3.0 | Verified Real Photo |
| `arecanut` | Yes / Yes | 8,432 B | 95,328 B | `ac050ae8313c6cb1` | `9019fe11438b86c9` | `b537511795e19ac3` | CC BY-SA 4.0 | Verified Real Photo |
| `banana` | Yes / Yes | 7,118 B | 65,618 B | `161182820509c902` | `58024d7c3e6cda71` | `b63771e59199ab93` | CC BY-SA 3.0 | Verified Real Photo |
| `mango` | Yes / Yes | 4,006 B | 42,746 B | `52eca8737261c982` | `3b5622c06740a9b6` | `0906860f0f0f4d69` | CC BY-SA 3.0 | Verified Real Photo |
| `papaya` | Yes / Yes | 5,590 B | 42,656 B | `e034b6a39373d9d5` | `49712e39e314255d` | `1c2ca6632392d858` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `citrus` | Yes / Yes | 5,870 B | 40,452 B | `5cbe22cbde8c03aa` | `5464063345acf532` | `7378d9bda4243798` | CC BY 3.0 | Verified Real Photo |
| `apple` | Yes / Yes | 6,620 B | 55,124 B | `eb9ce290b2c382ab` | `901effb5f26b29cb` | `dad2a425d3526949` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `cocoa` | Yes / Yes | 6,978 B | 54,620 B | `4c7415669410dc4f` | `74ffca0235d0f45a` | `1c389892b2f2d1d1` | CC BY 3.0 | Verified Real Photo |
| `oil-palm` | Yes / Yes | 7,290 B | 91,344 B | `c87ad27f37208ad8` | `5ccabc79fb79e831` | `5a1b9bcc9cb8b836` | CC BY-SA 4.0 | Verified Real Photo |
| `rubber` | Yes / Yes | 6,982 B | 94,418 B | `d1edfb9230baaddb` | `62862053ee96b2ba` | `2f3b3a1e0d333303` | Public domain | Verified Real Photo |
| `alfalfa` | Yes / Yes | 4,558 B | 33,450 B | `d50d2d9be89b313b` | `296d2c275f1dc3e1` | `33a3eeb0799b92a4` | CC BY-SA 3.0 | Verified Real Photo |
| `napier-grass` | Yes / Yes | 5,980 B | 81,694 B | `2c44f6d0a780cc6c` | `7e004855dda60f1b` | `4144c86d2db9bb9b` | CC BY 3.0 | Verified Real Photo |
| `black-gram` | Yes / Yes | 7,858 B | 87,034 B | `3b59f4a5e058941a` | `9774bc04a9673215` | `9522adada6ae4505` | CC BY-SA 3.0 | Verified Real Photo |
| `fenugreek` | Yes / Yes | 9,764 B | 87,546 B | `81d85da686a6e02f` | `31a9590e35274aee` | `b56abdb55565a6a4` | CC BY-SA 3.0 | Verified Real Photo |
| `grape` | Yes / Yes | 6,922 B | 42,950 B | `030144ea70b1776e` | `b029c128c6c29cc3` | `5b850c9d990c8c85` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `paddy` | Yes / Yes | 5,126 B | 18,750 B | `6aac14c00fb1f3c4` | `cf6d6d0897f87de4` | `0015412080f8f8b8` | CC BY-SA 3.0 | Verified Real Photo |
| `areca-nut` | Yes / Yes | 5,168 B | 65,386 B | `5a42a4bb513e41c1` | `ea2d68066eff77f2` | `3a74f07272859251` | CC BY-SA 4.0 | Verified Real Photo |
| `vegetables` | Yes / Yes | 8,930 B | 81,660 B | `6ab40c81ada024dc` | `4cf1f1db284e8901` | `cbe4ccd26bcdb597` | Unsplash License (CC0-equivalent) | Verified Real Photo |
| `other` | Yes / Yes | 8,984 B | 86,768 B | `61561fdc66b51670` | `4a569f5a12c11ee3` | `991c6858cb451505` | Unsplash License (CC0-equivalent) | Verified Real Photo |

---

## 3. Catalog Availability (`src/data/crops-with-images.json`)

A crop is offered in the app only if both WebP files exist, the thumb is at least 3 KB, it is not a flat-colour tile (pixel stdev >= 18), and its SHA-256 / perceptual hash is not shared with another crop.

**60 of 60 crops available, 0 hidden.**

| Crop ID | Status | Reason |
| :--- | :---: | :--- |
| `rice` | Available | Proper image |
| `wheat` | Available | Proper image |
| `maize` | Available | Proper image |
| `sorghum` | Available | Proper image |
| `millet` | Available | Proper image |
| `barley` | Available | Proper image |
| `oats` | Available | Proper image |
| `chickpea` | Available | Proper image |
| `lentil` | Available | Proper image |
| `pigeon-pea` | Available | Proper image |
| `moong` | Available | Proper image |
| `cowpea` | Available | Proper image |
| `soybean` | Available | Proper image |
| `beans` | Available | Proper image |
| `peas` | Available | Proper image |
| `groundnut` | Available | Proper image |
| `mustard` | Available | Proper image |
| `sunflower` | Available | Proper image |
| `sesame` | Available | Proper image |
| `rapeseed` | Available | Proper image |
| `potato` | Available | Proper image |
| `sweet-potato` | Available | Proper image |
| `cassava` | Available | Proper image |
| `yam` | Available | Proper image |
| `onion` | Available | Proper image |
| `garlic` | Available | Proper image |
| `tomato` | Available | Proper image |
| `brinjal` | Available | Proper image |
| `chilli` | Available | Proper image |
| `cabbage` | Available | Proper image |
| `cauliflower` | Available | Proper image |
| `okra` | Available | Proper image |
| `cucumber` | Available | Proper image |
| `pumpkin` | Available | Proper image |
| `cotton` | Available | Proper image |
| `sugarcane` | Available | Proper image |
| `jute` | Available | Proper image |
| `tea` | Available | Proper image |
| `coffee` | Available | Proper image |
| `tobacco` | Available | Proper image |
| `coconut` | Available | Proper image |
| `cashew` | Available | Proper image |
| `arecanut` | Available | Proper image |
| `banana` | Available | Proper image |
| `mango` | Available | Proper image |
| `papaya` | Available | Proper image |
| `citrus` | Available | Proper image |
| `apple` | Available | Proper image |
| `cocoa` | Available | Proper image |
| `oil-palm` | Available | Proper image |
| `rubber` | Available | Proper image |
| `alfalfa` | Available | Proper image |
| `napier-grass` | Available | Proper image |
| `black-gram` | Available | Proper image |
| `fenugreek` | Available | Proper image |
| `grape` | Available | Proper image |
| `paddy` | Available | Proper image |
| `areca-nut` | Available | Proper image |
| `vegetables` | Available | Proper image |
| `other` | Available | Proper image |

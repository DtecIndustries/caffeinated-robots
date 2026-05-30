"""Run with: uv run list_cams.py — saves a snapshot per detected camera to .cam_check/"""
import cv2
import os

out_dir = ".cam_check"
os.makedirs(out_dir, exist_ok=True)

found = []
for i in range(10):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        ok, frame = cap.read()
        if ok:
            path = os.path.join(out_dir, f"cam_{i}.jpg")
            cv2.imwrite(path, frame)
            found.append(i)
            print(f"cam {i} → {path}")
        cap.release()

if not found:
    print("No cameras found.")
else:
    print(f"\nFound {len(found)} camera(s): {found}")
    print(f"Check .cam_check/ for snapshots, then set CAMERA_INDEX in .env")

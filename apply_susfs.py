#!/usr/bin/env python3
"""
Apply SUSFS (simonpunk/susfs4ksu kernel-5.4) to kernel source.
Must run BEFORE ReSukiSU manual hooks (patch_hooks.py).
Assumes susfs4ksu repo is cloned at ./susfs4ksu alongside kernel/.
"""
import os
import subprocess
import sys
import re

SUSFS_REPO = "susfs4ksu"
SUSFS_BRANCH = "kernel-5.4"

def run(cmd, cwd=None, check=True):
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.stdout.strip():
        for line in result.stdout.strip().split('\n')[:10]:
            print(f"    {line}")
    if result.returncode != 0 and check:
        print(f"    WARNING: exit code {result.returncode}")
        if result.stderr:
            for line in result.stderr.strip().split('\n')[:5]:
                print(f"    ERR: {line}")
    return result

def main():
    kernel_dir = os.environ.get("KERNEL_DIR", ".")
    
    print("=== Step 1: Clone susfs4ksu ===")
    if not os.path.exists(SUSFS_REPO):
        run(f"git clone --depth=1 -b {SUSFS_BRANCH} https://gitlab.com/simonpunk/susfs4ksu.git {SUSFS_REPO}")
    else:
        print("  susfs4ksu already cloned")
    
    susfs_patch_dir = f"{SUSFS_REPO}/kernel_patches"
    
    print("\n=== Step 2: Copy SUSFS source files to kernel tree ===")
    # Copy fs/susfs.c
    src_susfs_c = f"{susfs_patch_dir}/fs/susfs.c"
    dst_susfs_c = f"{kernel_dir}/fs/susfs.c"
    if os.path.exists(src_susfs_c):
        run(f"cp {src_susfs_c} {dst_susfs_c}")
        print("  Copied fs/susfs.c")
    else:
        print("  ERROR: susfs.c not found!")
        return 1
    
    # Copy include files
    for hdr in ["susfs.h", "susfs_def.h"]:
        src = f"{susfs_patch_dir}/include/linux/{hdr}"
        dst = f"{kernel_dir}/include/linux/{hdr}"
        if os.path.exists(src):
            run(f"cp {src} {dst}")
            print(f"  Copied include/linux/{hdr}")
        else:
            print(f"  ERROR: {hdr} not found!")
            return 1
    
    print("\n=== Step 3: Apply kernel patch ===")
    kernel_patch = f"{susfs_patch_dir}/50_add_susfs_in_kernel-5.4.patch"
    if os.path.exists(kernel_patch):
        # Use patch with fallback
        result = run(f"patch -p1 --no-backup-if-mismatch --forward < {kernel_patch}", 
                     cwd=kernel_dir, check=False)
        if result.returncode != 0:
            print("  Some hunks failed, trying with --force...")
            run(f"patch -p1 --no-backup-if-mismatch --force < {kernel_patch}", 
                cwd=kernel_dir, check=False)
    else:
        print(f"  ERROR: {kernel_patch} not found!")
        return 1
    
    print("\n=== Step 4: Apply KernelSU SUSFS enable patch ===")
    ksu_patch = f"{susfs_patch_dir}/KernelSU/10_enable_susfs_for_ksu.patch"
    ksu_dir = f"{kernel_dir}/KernelSU"
    if os.path.exists(ksu_patch) and os.path.isdir(ksu_dir):
        result = run(f"patch -p1 --no-backup-if-mismatch --forward < {ksu_patch}",
                     cwd=ksu_dir, check=False)
        if result.returncode != 0:
            print("  Some hunks failed, trying with --force...")
            run(f"patch -p1 --no-backup-if-mismatch --force < {ksu_patch}",
                cwd=ksu_dir, check=False)
    else:
        if not os.path.exists(ksu_patch):
            print(f"  WARNING: {ksu_patch} not found")
        if not os.path.isdir(ksu_dir):
            print(f"  WARNING: {ksu_dir} not found (ReSukiSU setup.sh may not have run yet)")
    
    print("\n=== Step 5: Add SUSFS config to defconfig fragment ===")
    susfs_configs = [
        "CONFIG_KSU_SUSFS=y",
        "CONFIG_KSU_SUSFS_HAS_MAGIC_MOUNT=y",
        "CONFIG_KSU_SUSFS_SUS_PATH=y",
        "CONFIG_KSU_SUSFS_SUS_MOUNT=y",
        "CONFIG_KSU_SUSFS_SUS_KSTAT=y",
        "CONFIG_KSU_SUSFS_TRY_UMOUNT=y",
        "CONFIG_KSU_SUSFS_SPOOF_UNAME=y",
        "CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG=y",
        "CONFIG_KSU_SUSFS_OPEN_REDIRECT=y",
        "# CONFIG_KSU_SUSFS_SUS_SU is not set",
        "CONFIG_KSU_SUSFS_ENABLE_LOG=y",
        "CONFIG_KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS=y",
    ]
    
    config_file = f"{kernel_dir}/arch/arm64/configs/vendor/susfs_fragment.config"
    with open(config_file, "w") as f:
        for cfg in susfs_configs:
            f.write(f"{cfg}\n")
    print(f"  Wrote {len(susfs_configs)} SUSFS configs to {config_file}")
    
    print("\n=== SUSFS integration complete ===")
    print("NOTE: ReSukiSU manual hooks (patch_hooks.py) should run AFTER this script.")
    print("The SUSFS kernel patch already includes ksu_handle_stat, ksu_handle_execveat,")
    print("ksu_handle_faccessat hooks in the relevant files.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

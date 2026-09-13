#!/usr/bin/env python3
"""Apply ReSukiSU manual hooks for non-GKI kernel 5.4."""
import sys

def read_file(path):
    with open(path, "r") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w") as f:
        f.write(content)

# ===== 1. fs/stat.c =====
print("Patching fs/stat.c...")
stat = read_file("fs/stat.c")

if "ksu_handle_stat" not in stat:
    stat_decl = (
        "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "__attribute__((hot))\n"
        "extern int ksu_handle_stat(int *dfd, const char __user **filename_user,\n"
        "\t\t\t\tint *flags);\n"
        "\n"
        "extern void ksu_handle_newfstat_ret(unsigned int *fd, struct stat __user **statbuf_ptr);\n"
        "#if defined(__ARCH_WANT_STAT64) || defined(__ARCH_WANT_COMPAT_STAT64)\n"
        "extern void ksu_handle_fstat64_ret(unsigned long *fd, struct stat64 __user **statbuf_ptr);\n"
        "#endif\n"
        "#endif\n\n"
    )
    marker = "SYSCALL_DEFINE4(newfstatat,"
    if marker in stat:
        idx = stat.index(marker)
        stat = stat[:idx] + stat_decl + stat[idx:]
        print("  Added stat hook declarations")

# Hook newfstatat
if "ksu_handle_stat(&dfd, &filename, &flag);" not in stat:
    marker = "SYSCALL_DEFINE4(newfstatat,"
    if marker in stat:
        idx = stat.index(marker)
        rest = stat[idx:]
        ei = rest.index("int error;")
        ins = idx + ei + len("int error;")
        hook = "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n\tksu_handle_stat(&dfd, &filename, &flag);\n#endif\n"
        stat = stat[:ins] + hook + stat[ins:]
        print("  Hooked newfstatat")

# Hook newfstat return
if "ksu_handle_newfstat_ret" not in stat:
    marker = "SYSCALL_DEFINE2(newfstat,"
    if marker in stat:
        idx = stat.index(marker)
        rest = stat[idx:]
        ri = rest.rindex("return error;")
        ins = idx + ri
        hook = "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n\tksu_handle_newfstat_ret(&fd, &statbuf);\n#endif\n"
        stat = stat[:ins] + hook + stat[ins:]
        print("  Hooked newfstat return")

# Hook fstatat64 (32-bit)
if "SYSCALL_DEFINE4(fstatat64," in stat and "ksu_handle_stat" not in stat[stat.index("SYSCALL_DEFINE4(fstatat64,"):]:
    marker = "SYSCALL_DEFINE4(fstatat64,"
    idx = stat.index(marker)
    rest = stat[idx:]
    ei = rest.index("int error;")
    ins = idx + ei + len("int error;")
    hook = "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n\tksu_handle_stat(&dfd, &filename, &flag);\n#endif\n"
    stat = stat[:ins] + hook + stat[ins:]
    print("  Hooked fstatat64")

# Hook fstat64 return (32-bit)
if "SYSCALL_DEFINE2(fstat64," in stat and "ksu_handle_fstat64_ret" not in stat:
    marker = "SYSCALL_DEFINE2(fstat64,"
    idx = stat.index(marker)
    rest = stat[idx:]
    ri = rest.rindex("return error;")
    ins = idx + ri
    hook = "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n\tksu_handle_fstat64_ret(&fd, &statbuf);\n#endif\n"
    stat = stat[:ins] + hook + stat[ins:]
    print("  Hooked fstat64 return")

write_file("fs/stat.c", stat)
print("  fs/stat.c DONE")

# ===== 2. fs/exec.c (kernel 3.14+ -> ksu_handle_execveat) =====
print("Patching fs/exec.c...")
exec_c = read_file("fs/exec.c")

if "ksu_handle_execveat" not in exec_c:
    decl = (
        "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "__attribute__((hot))\n"
        "extern int ksu_handle_execveat(int *fd, struct filename **filename_ptr,\n"
        "\t\t\t\tvoid *argv, void *envp, int *flags);\n"
        "#endif\n\n"
    )
    hook = (
        "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "\tksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);\n"
        "#endif\n"
    )

    marker = "static int do_execveat_common(int fd, struct filename *filename,"
    if marker in exec_c:
        idx = exec_c.index(marker)
        exec_c = exec_c[:idx] + decl + exec_c[idx:]
        print("  Added execveat declaration")

        idx2 = exec_c.index(marker)
        rest = exec_c[idx2:]
        ri = rest.index("return __do_execve_file(")
        ins = idx2 + ri
        exec_c = exec_c[:ins] + hook + exec_c[ins:]
        print("  Hooked do_execveat_common")
    else:
        print("  WARNING: do_execveat_common not found!")

write_file("fs/exec.c", exec_c)
print("  fs/exec.c DONE")

# ===== 3. fs/open.c (kernel 4.19+ pattern) =====
print("Patching fs/open.c...")
open_c = read_file("fs/open.c")

if "ksu_handle_faccessat" not in open_c:
    decl = (
        "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "__attribute__((hot))\n"
        "extern int ksu_handle_faccessat(int *dfd, const char __user **filename_user,\n"
        "\t\t\t\tint *mode, int *flags);\n"
        "#endif\n\n"
    )
    hook = (
        "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "\tksu_handle_faccessat(&dfd, &filename, &mode, NULL);\n"
        "#endif\n"
    )

    marker = "SYSCALL_DEFINE3(faccessat,"
    if marker in open_c:
        idx = open_c.index(marker)
        open_c = open_c[:idx] + decl + open_c[idx:]

        idx2 = open_c.index(marker)
        rest = open_c[idx2:]
        brace = rest.index("{")
        ins = idx2 + brace + 1
        open_c = open_c[:ins] + hook + open_c[ins:]
        print("  Hooked faccessat")
    else:
        print("  WARNING: SYSCALL_DEFINE3(faccessat not found!")

write_file("fs/open.c", open_c)
print("  fs/open.c DONE")

# ===== 4. kernel/reboot.c (kernel 3.11+) =====
print("Patching kernel/reboot.c...")
reboot_c = read_file("kernel/reboot.c")

if "ksu_handle_sys_reboot" not in reboot_c:
    decl = (
        "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "extern int ksu_handle_sys_reboot(int magic1, int magic2, unsigned int cmd, void __user **arg);\n"
        "#endif\n\n"
    )
    hook = (
        "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "\tksu_handle_sys_reboot(magic1, magic2, cmd, &arg);\n"
        "#endif\n"
    )

    marker = "SYSCALL_DEFINE4(reboot, int, magic1, int, magic2, unsigned int, cmd,"
    if marker in reboot_c:
        idx = reboot_c.index(marker)
        reboot_c = reboot_c[:idx] + decl + reboot_c[idx:]

        idx2 = reboot_c.index(marker)
        rest = reboot_c[idx2:]
        ri = rest.index("int ret = 0;")
        ins = idx2 + ri + len("int ret = 0;")
        reboot_c = reboot_c[:ins] + hook + reboot_c[ins:]
        print("  Hooked reboot syscall")
    else:
        print("  WARNING: SYSCALL_DEFINE4(reboot not found!")

write_file("kernel/reboot.c", reboot_c)
print("  kernel/reboot.c DONE")

print("\nAll manual hooks applied successfully!")

# ===== Fix bare #elif in taskstats.c (clang rejects, GCC accepts) =====
print("\nFixing bare #elif in taskstats.c...")
try:
    with open("kernel/taskstats.c", "r") as f:
        content = f.read()
    # Replace bare #elif (no condition) with #else
    import re
    new_content = re.sub(r'^(\s*)#elif\s*$', r'\1#else', content, flags=re.MULTILINE)
    if new_content != content:
        with open("kernel/taskstats.c", "w") as f:
            f.write(new_content)
        print("  Fixed bare #elif -> #else in taskstats.c")
    else:
        print("  taskstats.c: no bare #elif found")
except Exception as e:
    print(f"  taskstats.c fix skipped: {e}")

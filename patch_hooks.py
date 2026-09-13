#!/usr/bin/env python3
"""
ReSukiSU manual integration hooks + compilation fixes for crDroid sm6375 (5.4.280).
Follows the official manual-integrate guide (resukisu.org/guide/manual-integrate.html).
Also includes SUSFS kernel patch compatibility.
"""
import re

def read_file(path):
    with open(path, "r") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w") as f:
        f.write(content)

print("=== Applying ReSukiSU manual hooks ===")

# ===== 1. fs/stat.c : ksu_handle_stat + ksu_handle_newfstat_ret + ksu_handle_fstat64_ret =====
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
    marker = "#if !defined(__ARCH_WANT_STAT64) || defined(__ARCH_WANT_SYS_NEWFSTATAT)"
    if marker in stat:
        idx = stat.index(marker)
        stat = stat[:idx] + stat_decl + stat[idx:]
    else:
        # fallback: before SYSCALL_DEFINE4(newfstatat
        marker = "SYSCALL_DEFINE4(newfstatat,"
        idx = stat.index(marker)
        stat = stat[:idx] + stat_decl + stat[idx:]
    print("  Added stat hook declarations")

if "ksu_handle_stat(&dfd, &filename, &flag);" not in stat:
    marker = "SYSCALL_DEFINE4(newfstatat,"
    idx = stat.index(marker)
    rest = stat[idx:]
    ei = rest.index("int error;")
    ins = idx + ei + len("int error;")
    hook = "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n\tksu_handle_stat(&dfd, &filename, &flag);\n#endif\n"
    stat = stat[:ins] + hook + stat[ins:]
    print("  Hooked newfstatat")

if "ksu_handle_newfstat_ret" not in stat:
    marker = "SYSCALL_DEFINE2(newfstat,"
    idx = stat.index(marker)
    rest = stat[idx:]
    ri = rest.rindex("return error;")
    ins = idx + ri
    hook = "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n\tksu_handle_newfstat_ret(&fd, &statbuf);\n#endif\n"
    stat = stat[:ins] + hook + stat[ins:]
    print("  Hooked newfstat return")

if "SYSCALL_DEFINE4(fstatat64," in stat and "ksu_handle_stat" not in stat[stat.index("SYSCALL_DEFINE4(fstatat64,"):]:
    marker = "SYSCALL_DEFINE4(fstatat64,"
    idx = stat.index(marker)
    rest = stat[idx:]
    ei = rest.index("int error;")
    ins = idx + ei + len("int error;")
    hook = "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n\tksu_handle_stat(&dfd, &filename, &flag);\n#endif\n"
    stat = stat[:ins] + hook + stat[ins:]
    print("  Hooked fstatat64")

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

# ===== 2. fs/exec.c : ksu_handle_execveat =====
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
        # add decl before the function (find previous blank / __do_execve_file end)
        decl_marker = "__do_execve_file(fd, filename, argv, envp, flags, NULL);\n}"
        di = exec_c.index(decl_marker) + len(decl_marker)
        exec_c = exec_c[:di] + "\n" + decl + exec_c[di:]
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

# ===== 3. fs/open.c : ksu_handle_faccessat =====
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

# ===== 4. kernel/reboot.c : ksu_handle_sys_reboot =====
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

# ===== 5. kernel/sys.c : ksu_handle_setresuid (required for 5.4, <6.8) =====
print("Patching kernel/sys.c...")
sys_c = read_file("kernel/sys.c")

if "ksu_handle_setresuid" not in sys_c:
    decl = (
        "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "extern int ksu_handle_setresuid(uid_t ruid, uid_t euid, uid_t suid);\n"
        "#endif\n\n"
    )
    hook = (
        "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "\t(void)ksu_handle_setresuid(ruid, euid, suid);\n"
        "#endif\n"
    )
    # 5.4 uses __sys_setresuid (4.17+)
    marker = "long __sys_setresuid(uid_t ruid, uid_t euid, uid_t suid)"
    if marker in sys_c:
        idx = sys_c.index(marker)
        sys_c = sys_c[:idx] + decl + sys_c[idx:]
        idx2 = sys_c.index(marker)
        rest = sys_c[idx2:]
        brace = rest.index("{")
        ins = idx2 + brace + 1
        sys_c = sys_c[:ins] + hook + sys_c[ins:]
        print("  Hooked __sys_setresuid")
    else:
        print("  WARNING: __sys_setresuid not found!")

write_file("kernel/sys.c", sys_c)
print("  kernel/sys.c DONE")

# ===== 6. fs/read_write.c : ksu_handle_sys_read (required for 5.4, <6.8) =====
print("Patching fs/read_write.c...")
rw_c = read_file("fs/read_write.c")

if "ksu_init_rc_hook" not in rw_c:
    decl = (
        "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "extern bool ksu_init_rc_hook __read_mostly;\n"
        "extern __attribute__((cold)) int ksu_handle_sys_read(unsigned int fd,\n"
        "\t\t\t\tchar __user **buf_ptr, size_t *count_ptr);\n"
        "#endif\n\n"
    )
    hook = (
        "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "\tif (unlikely(ksu_init_rc_hook))\n"
        "\t\tksu_handle_sys_read(fd, &buf, &count);\n"
        "#endif\n"
    )
    marker = "SYSCALL_DEFINE3(read, unsigned int, fd, char __user *, buf, size_t, count)"
    if marker in rw_c:
        idx = rw_c.index(marker)
        rw_c = rw_c[:idx] + decl + rw_c[idx:]
        idx2 = rw_c.index(marker)
        rest = rw_c[idx2:]
        brace = rest.index("{")
        ins = idx2 + brace + 1
        rw_c = rw_c[:ins] + hook + rw_c[ins:]
        print("  Hooked sys_read")
    else:
        print("  WARNING: SYSCALL_DEFINE3(read not found!")

write_file("fs/read_write.c", rw_c)
print("  fs/read_write.c DONE")

# ===== 7. drivers/input/input.c : ksu_handle_input_handle_event (required for 5.4) =====
print("Patching drivers/input/input.c...")
input_c = read_file("drivers/input/input.c")

if "ksu_handle_input_handle_event" not in input_c:
    decl = (
        "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "extern bool ksu_input_hook __read_mostly;\n"
        "extern __attribute__((cold)) int ksu_handle_input_handle_event(\n"
        "\t\t\tunsigned int *type, unsigned int *code, int *value);\n"
        "#endif\n\n"
    )
    hook = (
        "\n#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "\tif (unlikely(ksu_input_hook))\n"
        "\t\tksu_handle_input_handle_event(&type, &code, &value);\n"
        "#endif\n"
    )
    marker = "void input_event(struct input_dev *dev,"
    if marker in input_c:
        idx = input_c.index(marker)
        input_c = input_c[:idx] + decl + input_c[idx:]
        idx2 = input_c.index(marker)
        rest = input_c[idx2:]
        brace = rest.index("{")
        ins = idx2 + brace + 1
        input_c = input_c[:ins] + hook + input_c[ins:]
        print("  Hooked input_event")
    else:
        print("  WARNING: input_event not found!")

write_file("drivers/input/input.c", input_c)
print("  drivers/input/input.c DONE")

# ===== 8. SELinux static exports (CONFIG_KALLSYMS_ALL is on, but add anyway for safety) =====
print("Patching SELinux exports...")

# 8a. security/selinux/selinuxfs.c: write_op + sel_handle_status_ops + sel_mutex
try:
    selinuxfs_c = read_file("security/selinux/selinuxfs.c")
    changed = False
    if "static ssize_t (*write_op[])(struct file *, char *, size_t) = {" in selinuxfs_c:
        selinuxfs_c = selinuxfs_c.replace(
            "static ssize_t (*write_op[])(struct file *, char *, size_t) = {",
            "ssize_t (*write_op[])(struct file *, char *, size_t) = {")
        changed = True
    if "static const struct file_operations sel_handle_status_ops = {" in selinuxfs_c:
        selinuxfs_c = selinuxfs_c.replace(
            "static const struct file_operations sel_handle_status_ops = {",
            "const struct file_operations sel_handle_status_ops = {")
        changed = True
    if "static DEFINE_MUTEX(sel_mutex);" in selinuxfs_c:
        selinuxfs_c = selinuxfs_c.replace(
            "static DEFINE_MUTEX(sel_mutex);",
            "DEFINE_MUTEX(sel_mutex);")
        changed = True
    if changed:
        write_file("security/selinux/selinuxfs.c", selinuxfs_c)
        print("  Exported write_op/sel_handle_status_ops/sel_mutex")
    else:
        print("  selinuxfs.c: exports already applied or patterns differ")
except Exception as e:
    print(f"  selinuxfs.c export skipped: {e}")

# 8b. security/selinux/ss/services.c: policy_rwlock
try:
    services_c = read_file("security/selinux/ss/services.c")
    if "static DEFINE_RWLOCK(policy_rwlock);" in services_c:
        services_c = services_c.replace(
            "static DEFINE_RWLOCK(policy_rwlock);",
            "DEFINE_RWLOCK(policy_rwlock);")
        write_file("security/selinux/ss/services.c", services_c)
        print("  Exported policy_rwlock")
    else:
        print("  services.c: policy_rwlock already exported or pattern differs")
except Exception as e:
    print(f"  services.c export skipped: {e}")

# 8c. security/selinux/hooks.c: selinux_ops
try:
    hooks_c = read_file("security/selinux/hooks.c")
    if "static struct security_operations selinux_ops = {" in hooks_c:
        hooks_c = hooks_c.replace(
            "static struct security_operations selinux_ops = {",
            "struct security_operations selinux_ops = {")
        write_file("security/selinux/hooks.c", hooks_c)
        print("  Exported selinux_ops")
    else:
        print("  hooks.c: selinux_ops already exported or pattern differs")
except Exception as e:
    print(f"  hooks.c export skipped: {e}")

print("\n=== ReSukiSU manual hooks applied ===")

print("\n=== Applying compilation fixes ===")

# Fix A: bare #elif in taskstats.c
try:
    content = read_file("kernel/taskstats.c")
    new_content = re.sub(r'^(\s*)#elif\s*$', r'\1#else', content, flags=re.MULTILINE)
    if new_content != content:
        write_file("kernel/taskstats.c", new_content)
        print("  Fixed bare #elif -> #else in taskstats.c")
    else:
        print("  taskstats.c: no bare #elif found")
except Exception as e:
    print(f"  taskstats.c fix skipped: {e}")

# Fix B: gcc-qcs404.c undeclared identifiers
try:
    content = read_file("drivers/clk/qcom/gcc-qcs404.c")
    if "P_GPLL0_OUT_AUX" in content:
        write_file("drivers/clk/qcom/gcc-qcs404.c.bak", content)
        write_file("drivers/clk/qcom/gcc-qcs404.c", "// Disabled: undeclared identifiers with LLVM build\n#if 0\n" + content + "\n#endif\n")
        print("  Wrapped gcc-qcs404.c in #if 0")
except Exception as e:
    print(f"  gcc-qcs404.c fix skipped: {e}")

# Fix C: qrtr/tun.c wrong arg count
try:
    content = read_file("net/qrtr/tun.c")
    if "QRTR_EP_NET_ID_AUTO, 0)" in content:
        content = content.replace("QRTR_EP_NET_ID_AUTO, 0)", "QRTR_EP_NET_ID_AUTO, 0, NULL)")
        write_file("net/qrtr/tun.c", content)
        print("  Fixed qrtr/tun.c: added 4th argument")
except Exception as e:
    print(f"  qrtr/tun.c fix skipped: {e}")

# Fix D: minstrel duplicate symbols
try:
    content = read_file("net/mac80211/Makefile")
    content = re.sub(r'rc80211_minstrel-y\s*:=\s*\\?\n?\s*rc80211_minstrel\.o\s*\\?\n?\s*rc80211_minstrel_ht\.o\$?\n?', '', content)
    content = re.sub(r'rc80211_minstrel-\$\(CONFIG_MAC80211_DEBUGFS\)\s*\+=\s*\\?\n?\s*rc80211_minstrel_debugfs\.o\s*\\?\n?\s*rc80211_minstrel_ht_debugfs\.o\$?\n?', '', content)
    content = content.replace(
        'mac80211-$(CONFIG_MAC80211_RC_MINSTREL) += $(rc80211_minstrel-y)',
        'mac80211-$(CONFIG_MAC80211_RC_MINSTREL) += rc80211_minstrel.o rc80211_minstrel_ht.o')
    write_file("net/mac80211/Makefile", content)
    print("  Fixed minstrel duplicates")
except Exception as e:
    print(f"  minstrel fix: {e}")

# Fix E: qcom_scm.c redefinition
try:
    content = read_file("drivers/firmware/qcom_scm.c")
    pattern = r'(subsys_initcall\(qcom_scm_init\);)'
    new_content = re.sub(pattern, r'#ifndef MODULE\n\1\n#endif', content)
    if new_content != content:
        write_file("drivers/firmware/qcom_scm.c", new_content)
        print("  Fixed qcom_scm.c subsys_initcall")
    else:
        print("  qcom_scm.c: already fixed")
except Exception as e:
    print(f"  qcom_scm.c fix: {e}")

# Fix F: stmmac_main.c missing decls
try:
    content = read_file("drivers/net/ethernet/stmicro/stmmac/stmmac_main.c")
    marker = "len += buf2_len;"
    if "unsigned int buf_len = len - prev_len;" in content and marker in content:
        idx = content.index(marker) + len(marker)
        decl = "\n\t\tunsigned int prev_len = len - buf1_len - buf2_len;\n\t\tunsigned int sec_len = buf2_len;"
        content = content[:idx] + decl + content[idx:]
        write_file("drivers/net/ethernet/stmicro/stmmac/stmmac_main.c", content)
        print("  Fixed stmmac_main.c prev_len/sec_len")
except Exception as e:
    print(f"  stmmac_main.c fix skipped: {e}")

print("\nAll hooks and fixes applied.")
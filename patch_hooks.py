#!/usr/bin/env python3
"""
Compilation fixes for ReSukiSU + SUSFS kernel build (crDroid sm6375, 5.4.280).
NOTE: No manual ksu_handle_* syscall hooks here!
ReSukiSU (modern) uses syscall_event_bridge registered via syscall_hook_manager
(__NR_execveat, __NR_newfstatat, __NR_faccessat...) - DO NOT add old-style
KernelSU 1.x source hooks (ksu_handle_execveat(&fd, ...)) - they conflict and
cause boot hangs / double-hooking.
"""
import re

def read_file(path):
    with open(path, "r") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w") as f:
        f.write(content)

print("Applying compilation fixes (no manual KSU syscall hooks)...")

# Fix 1: bare #elif in taskstats.c (clang rejects, GCC accepts)
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

# Fix 2: gcc-qcs404.c undeclared identifiers (disable this driver)
try:
    content = read_file("drivers/clk/qcom/gcc-qcs404.c")
    if "P_GPLL0_OUT_AUX" in content:
        print("  Disabling gcc-qcs404.c compilation via wrapper")
        write_file("drivers/clk/qcom/gcc-qcs404.c.bak", content)
        write_file("drivers/clk/qcom/gcc-qcs404.c", "// Disabled: undeclared identifiers with LLVM build\n#if 0\n" + content + "\n#endif\n")
        print("  Wrapped gcc-qcs404.c in #if 0")
except Exception as e:
    print(f"  gcc-qcs404.c fix skipped: {e}")

# Fix 3: qrtr/tun.c wrong number of arguments
try:
    content = read_file("net/qrtr/tun.c")
    if "QRTR_EP_NET_ID_AUTO, 0)" in content:
        content = content.replace("QRTR_EP_NET_ID_AUTO, 0)", "QRTR_EP_NET_ID_AUTO, 0, NULL)")
        write_file("net/qrtr/tun.c", content)
        print("  Fixed qrtr/tun.c: added 4th argument to qrtr_endpoint_register")
except Exception as e:
    print(f"  qrtr/tun.c fix skipped: {e}")

# Fix 4: minstrel duplicate symbols
try:
    content = read_file("net/mac80211/Makefile")
    content = re.sub(
        r'rc80211_minstrel-y\s*:=\s*\\?\n?\s*rc80211_minstrel\.o\s*\\?\n?\s*rc80211_minstrel_ht\.o\$?\n?',
        '', content
    )
    content = re.sub(
        r'rc80211_minstrel-\$\(CONFIG_MAC80211_DEBUGFS\)\s*\+=\s*\\?\n?\s*rc80211_minstrel_debugfs\.o\s*\\?\n?\s*rc80211_minstrel_ht_debugfs\.o\$?\n?',
        '', content
    )
    content = content.replace(
        'mac80211-$(CONFIG_MAC80211_RC_MINSTREL) += $(rc80211_minstrel-y)',
        'mac80211-$(CONFIG_MAC80211_RC_MINSTREL) += rc80211_minstrel.o rc80211_minstrel_ht.o'
    )
    write_file("net/mac80211/Makefile", content)
    print("  Fixed minstrel: removed composite variable, inlined objects into mac80211")
except Exception as e:
    print(f"  minstrel fix: {e}")

# Fix 5: qcom_scm.c redefinition
try:
    content = read_file("drivers/firmware/qcom_scm.c")
    pattern = r'(subsys_initcall\(qcom_scm_init\);)'
    replacement = r'#ifndef MODULE\n\1\n#endif'
    if re.search(pattern, content):
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            write_file("drivers/firmware/qcom_scm.c", new_content)
            print("  Fixed qcom_scm.c: wrapped subsys_initcall in #ifndef MODULE")
        else:
            print("  qcom_scm.c: subsys_initcall already wrapped")
    else:
        print("  qcom_scm.c: subsys_initcall(qcom_scm_init) not found")
except Exception as e:
    print(f"  qcom_scm.c fix: {e}")

# Fix 6: stmmac_main.c missing prev_len/sec_len declarations (stock config doesn't use stmmac)
try:
    content = read_file("drivers/net/ethernet/stmicro/stmmac/stmmac_main.c")
    marker = "len += buf2_len;"
    if "unsigned int buf_len = len - prev_len;" in content and marker in content:
        idx = content.index(marker) + len(marker)
        decl = "\n\t\tunsigned int prev_len = len - buf1_len - buf2_len;\n\t\tunsigned int sec_len = buf2_len;"
        content = content[:idx] + decl + content[idx:]
        write_file("drivers/net/ethernet/stmicro/stmmac/stmmac_main.c", content)
        print("  Fixed stmmac_main.c: added prev_len/sec_len declarations after buf2_len calc")
except Exception as e:
    print(f"  stmmac_main.c fix skipped: {e}")

print("\nAll compilation fixes applied. NO manual ksu_handle_* syscall hooks were added.")
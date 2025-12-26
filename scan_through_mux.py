#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import SLABHIDtoSMBUS as hid
import ctypes as ct
import time

def scan_through_mux():
    smb = hid.HidSmbusDevice()
    _lib = hid._DLL
    
    # --- 必須: 型定義の修正パッチ ---
    _lib.HidSmbus_GetReadResponse.argtypes = [
        ct.c_void_p, ct.POINTER(ct.c_ubyte), ct.c_char_p, ct.c_ubyte, ct.POINTER(ct.c_ubyte)
    ]
    _lib.HidSmbus_GetReadResponse.restype = ct.c_int

    print("--- Scanning I2C Bus via TCA9548A Channel 1 ---")

    try:
        smb.Open(0)
        # タイムアウトと設定（AutoRead=True）
        smb.SetTimeouts(200)
        smb.SetSmbusConfig(100000, 0x02, True, 200, 200, False, 2)

        # 1. Muxを Channel 1 にセット
        MUX_ADDR = 0x70 << 1
        print("Setting Mux to Channel 1...")
        smb.WriteRequest(MUX_ADDR, [0x02], 1)
        time.sleep(0.1)

        # 2. スキャン開始
        print("     0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F")
        print("00:                         ", end="", flush=True)
        found_devices = []

        for addr in range(0x08, 0x78): # 0x08 - 0x77
            if addr % 16 == 0:
                print(f"{addr:02x}: ", end="", flush=True)

            target_addr = addr << 1
            
            # Mux自身(0x70)はスキップしても良いが、確認のため表示
            
            try:
                # 1バイト読み出しを試行
                smb.ReadRequest(target_addr, 1)
                
                # データ受信待ち
                buf = ct.create_string_buffer(64)
                status = ct.c_ubyte(0)
                num_bytes_read = ct.c_ubyte(0)
                
                res = _lib.HidSmbus_GetReadResponse(
                    smb.handle, ct.byref(status), buf, ct.c_ubyte(64), ct.byref(num_bytes_read)
                )
                
                # 0x00(Success) または 読み取りバイトがある場合
                if res == 0 and status.value == hid.HID_SMBUS_S0.COMPLETE:
                    print(f"{addr:02x} ", end="", flush=True)
                    found_devices.append(hex(addr))
                else:
                    print("-- ", end="", flush=True)

            except Exception:
                print("-- ", end="", flush=True)

            if (addr + 1) % 16 == 0:
                print()

        print(f"\nScan complete. Found: {', '.join(found_devices)}")
        
        # Mux以外のアドレスが見つかれば、それがリレーボードです
        for dev in found_devices:
            if dev != '0x70':
                print(f"-> TARGET DEVICE detected at: {dev}")

    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if smb.IsOpened():
            smb.Close()

if __name__ == "__main__":
    scan_through_mux()

# __END__

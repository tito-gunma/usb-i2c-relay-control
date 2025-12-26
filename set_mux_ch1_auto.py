#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import SLABHIDtoSMBUS as hid
import ctypes as ct
import time

def set_mux_channel_auto():
    smb = hid.HidSmbusDevice()
    _lib = hid._DLL
    
    # --- [重要] DLL関数の型定義修正 ---
    # これを行わないと64bit環境でデータが空(0)になる問題が発生するため維持します
    _lib.HidSmbus_GetReadResponse.argtypes = [
        ct.c_void_p, ct.POINTER(ct.c_ubyte), ct.c_char_p, ct.c_ubyte, ct.POINTER(ct.c_ubyte)
    ]
    _lib.HidSmbus_GetReadResponse.restype = ct.c_int

    # アドレス設定 (0x70 -> 0xE0)
    MUX_ADDR_8BIT = 0x70 << 1
    CMD_VALUE = 0x02

    print(f"--- TCA9548A Setup (Auto-Read Mode) ---")

    try:
        smb.Open(0)
        
        # 1. タイムアウト設定 (USB応答待ち時間を1秒に延長)
        smb.SetTimeouts(1000)

        # 2. SMBus設定 (AutoReadRespond = True に変更)
        # これにより、ReadRequest完了後に自動的にデータがPCに送られます
        # 引数: (bitRate, address, autoReadRespond, writeTimeout, readTimeout, ...)
        smb.SetSmbusConfig(100000, 0x02, True, 1000, 1000, False, 3)

        # 3. 書き込み (Channel 1 選択)
        print(f"Writing 0x{CMD_VALUE:02X}...")
        smb.WriteRequest(MUX_ADDR_8BIT, [CMD_VALUE], 1)
        
        # 書き込み完了を少し待つ (書き込みはすぐに終わるため単純なsleepで十分)
        time.sleep(0.1)

        # 4. 読み出しリクエスト
        print("Requesting data...")
        smb.ReadRequest(MUX_ADDR_8BIT, 1)

        # 5. データ受信 (ステータス確認ループを廃止し、直接データを待つ)
        # autoReadRespond=Trueの場合、ReadRequest後すぐにGetReadResponseを呼ぶのが正解
        print("Waiting for response...")
        
        buf_size = 64
        buf = ct.create_string_buffer(buf_size)
        status = ct.c_ubyte(0)
        num_bytes_read = ct.c_ubyte(0)
        
        # この関数はデータが来るまで最大Timeout時間(1秒)ブロックします
        res = _lib.HidSmbus_GetReadResponse(
            smb.handle, 
            ct.byref(status), 
            buf, 
            ct.c_ubyte(buf_size), 
            ct.byref(num_bytes_read)
        )

        if res == 0:
            actual_len = num_bytes_read.value
            data_bytes = buf.raw[:actual_len]
            print(f"Status: 0x{status.value:02X}, Bytes: {actual_len}, Data: {data_bytes}")
            
            if actual_len > 0:
                val = data_bytes[0]
                print(f"Read Value: 0x{val:02X}")
                if val == CMD_VALUE:
                    print("SUCCESS: Channel 1 is ACTIVE.")
                else:
                    print(f"WARNING: Value mismatch (Got 0x{val:02X})")
            else:
                print("ERROR: Receive succeeded but data is empty.")
        else:
            # エラー 0x12 が出る場合は、物理的な配線や電源の問題の可能性も出てきます
            print(f"DLL Error Code: {hex(res)}")
            if res == 0x12:
                print(" -> Timeout waiting for data from device.")

    except Exception as e:
        print(f"System Error: {e}")
        
    finally:
        if smb.IsOpened():
            smb.Close()
            print("Device closed.")

if __name__ == "__main__":
    set_mux_channel_auto()

# __END__

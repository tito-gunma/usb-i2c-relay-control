#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import SLABHIDtoSMBUS as hid
import ctypes as ct
import time

def relay_control_manual():
    smb = hid.HidSmbusDevice()
    _lib = hid._DLL
    
    # -------------------------------------------------------------
    # 型定義パッチ
    # -------------------------------------------------------------
    _lib.HidSmbus_GetReadResponse.argtypes = [
        ct.c_void_p, ct.POINTER(ct.c_ubyte), ct.c_char_p, ct.c_ubyte, ct.POINTER(ct.c_ubyte)
    ]
    _lib.HidSmbus_GetReadResponse.restype = ct.c_int

    # アドレス
    MUX_ADDR  = 0x70 << 1
    MCP_ADDR  = 0x20 << 1
    
    # レジスタ
    REG_IODIRA = 0x00
    REG_GPIOA  = 0x12

    print("--- MCP23017 Relay Control (Manual Mode) ---")

    try:
        smb.Open(0)
        # タイムアウト設定
        smb.SetTimeouts(1000)
        
        # [重要] AutoReadRespond = False (手動モード)
        # これにより、勝手にデータが送られてくるのを防ぎ、確実に取得します
        smb.SetSmbusConfig(100000, 0x02, False, 1000, 1000, False, 3)

        # ---------------------------------------------------------
        # 1. Mux 設定 (Channel 1)
        # ---------------------------------------------------------
        print("1. Setting Mux to Channel 1...")
        smb.WriteRequest(MUX_ADDR, [0x02], 1)
        time.sleep(0.1)

        # ---------------------------------------------------------
        # 2. 初期設定 (全出力, 初期値OFF)
        # ---------------------------------------------------------
        print("2. Configuring MCP23017...")
        # まず出力を 0xFF (OFF) に
        smb.WriteRequest(MCP_ADDR, [REG_GPIOA, 0xFF], 2)
        smb.WriteRequest(MCP_ADDR, [0x13, 0xFF], 2) # GPIOB
        # 方向を出力 (0x00) に
        smb.WriteRequest(MCP_ADDR, [REG_IODIRA, 0x00], 2)
        smb.WriteRequest(MCP_ADDR, [0x01, 0x00], 2) # IODIRB
        time.sleep(0.1)

        # ---------------------------------------------------------
        # 3. リレー制御テスト (0xAA 書き込み)
        # ---------------------------------------------------------
        TEST_VAL = 0xAA
        print(f"3. Writing 0x{TEST_VAL:02X} to GPIOA...")
        smb.WriteRequest(MCP_ADDR, [REG_GPIOA, TEST_VAL], 2)
        
        # 書き込み完了待ち
        time.sleep(0.1)
        
        # ---------------------------------------------------------
        # 4. 検証読み出し (手動モード)
        # ---------------------------------------------------------
        print("4. Verifying (Manual Read)...")
        
        # (A) 読み取りリクエスト送信 (I2Cバス上でデータを読む)
        reg_bytes = bytes([REG_GPIOA])
        offset_buf = ct.create_string_buffer(reg_bytes, 16)
        smb.AddressReadRequest(MCP_ADDR, 1, 1, offset_buf)
        
        # (B) 完了待ち
        read_ready = False
        for _ in range(50):
            time.sleep(0.01)
            smb.TransferStatusRequest()
            s0, s1, _, bytes_read = smb.GetTransferStatusResponse()
            if s0 == hid.HID_SMBUS_S0.COMPLETE:
                read_ready = True
                break
        
        if read_ready:
            # (C) [重要] ForceReadResponse でデータを要求
            # CP2112のバッファにあるデータをUSBで送れと指示する
            smb.ForceReadResponse(1) # 1バイト送れ
            
            # (D) データ受信
            # ForceReadResponseの直後に GetReadResponse を呼ぶ
            time.sleep(0.01)
            buf = ct.create_string_buffer(64)
            st = ct.c_ubyte(0)
            n = ct.c_ubyte(0)
            
            _lib.HidSmbus_GetReadResponse(smb.handle, ct.byref(st), buf, ct.c_ubyte(64), ct.byref(n))
            
            if n.value > 0:
                val = buf.raw[0]
                # int変換 (Pythonバージョン差異吸収)
                if isinstance(val, str): val = ord(val)
                
                print(f"   Read Result: 0x{val:02X}")
                if val == TEST_VAL:
                    print("   -> SUCCESS: Values match! Control Logic Complete.")
                else:
                    print(f"   -> MISMATCH: Expected 0x{TEST_VAL:02X}")
            else:
                print(f"   Error: No data received after ForceReadResponse. (Status: {hex(st.value)})")
        else:
            print("   Error: Read Transaction Timeout on I2C bus.")

    except Exception as e:
        print(f"System Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if smb.IsOpened():
            # テスト終了後、安全のため全OFFにするならコメントアウトを外す
            # smb.WriteRequest(MCP_ADDR, [REG_GPIOA, 0xFF], 2)
            smb.Close()
            print("Device closed.")

if __name__ == "__main__":
    relay_control_manual()

# __END__

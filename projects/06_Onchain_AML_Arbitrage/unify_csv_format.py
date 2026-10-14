#!/usr/bin/env python3
"""
统一两个交易 CSV 文件的格式，使其兼容 neo4j-admin import。

处理内容：
1. transactions.csv: value 保持 string 类型，新增 block_number 列（空值）
2. usdt_transfers.csv: value 改为 string 类型，新增 hash 列（空值）
3. 所有文件表头标准化
"""

import csv
import os
import sys

# ============ 配置区域 ============
TRANSACTIONS_INPUT = "transactions.csv"
USDT_TRANSFERS_INPUT = "usdt_transfers.csv"

TRANSACTIONS_OUTPUT = "transactions_unified.csv"
USDT_TRANSFERS_OUTPUT = "usdt_transfers_unified.csv"

# 可选：同时检查并修正节点文件（确保表头正确）
NODES_INPUTS = ["nodes_addresses.csv", "usdt_addresses.csv"]
NODES_OUTPUTS = ["nodes_addresses_fixed.csv", "usdt_addresses_fixed.csv"]
# =================================


def fix_transactions_file():
    """
    修复 transactions.csv:
    - 表头：:START_ID(Address),:END_ID(Address),value:string,hash,block_number:int
    - 新增 block_number 列，所有值填为空字符串
    - value 列保持 string 类型（用 :string 标记）
    """
    print("📄 处理 transactions.csv...")
    
    try:
        with open(TRANSACTIONS_INPUT, 'r', encoding='utf-8') as infile, \
             open(TRANSACTIONS_OUTPUT, 'w', encoding='utf-8', newline='') as outfile:
            
            reader = csv.reader(infile)
            writer = csv.writer(outfile)
            
            # 读取原始表头
            original_header = next(reader)
            print(f"   原始表头: {original_header}")
            
            # 写入新表头（注意 value 标记为 string，新增 block_number:int）
            new_header = [
                ':START_ID(Address)',
                ':END_ID(Address)',
                'value:string',
                'hash',
                'block_number:int'
            ]
            writer.writerow(new_header)
            
            # 处理数据行
            row_count = 0
            for row in reader:
                # 假设原始顺序: from, to, value, hash
                # 根据实际顺序调整！你的 CSV 是 :START_ID,:END_ID,value,hash
                if len(row) >= 4:
                    start_id = row[0].strip()
                    end_id = row[1].strip()
                    value = row[2].strip()
                    tx_hash = row[3].strip()
                    
                    # 新增 block_number 列，填充空字符串（表示未知）
                    block_number = ''
                    
                    writer.writerow([start_id, end_id, value, tx_hash, block_number])
                    row_count += 1
            
            print(f"   ✅ 完成！共处理 {row_count} 行，输出文件: {TRANSACTIONS_OUTPUT}")
            
    except FileNotFoundError:
        print(f"   ❌ 错误：找不到文件 {TRANSACTIONS_INPUT}，请检查路径")
        sys.exit(1)
    except Exception as e:
        print(f"   ❌ 处理失败: {e}")
        sys.exit(1)


def fix_usdt_transfers_file():
    """
    修复 usdt_transfers.csv:
    - 表头：:START_ID(Address),:END_ID(Address),value:string,hash,block_number:int
    - 新增 hash 列，所有值填为空字符串
    - value 列从 long 改为 string（去掉 :long，改为 :string）
    """
    print("\n📄 处理 usdt_transfers.csv...")
    
    try:
        with open(USDT_TRANSFERS_INPUT, 'r', encoding='utf-8') as infile, \
             open(USDT_TRANSFERS_OUTPUT, 'w', encoding='utf-8', newline='') as outfile:
            
            reader = csv.reader(infile)
            writer = csv.writer(outfile)
            
            # 读取原始表头
            original_header = next(reader)
            print(f"   原始表头: {original_header}")
            
            # 写入新表头（统一格式）
            new_header = [
                ':START_ID(Address)',
                ':END_ID(Address)',
                'value:string',    # 改为 string 类型
                'hash',            # 新增 hash 列
                'block_number:int'
            ]
            writer.writerow(new_header)
            
            # 处理数据行
            row_count = 0
            for row in reader:
                # 原始格式: :START_ID,:END_ID,value,block_number
                if len(row) >= 4:
                    start_id = row[0].strip()
                    end_id = row[1].strip()
                    value = row[2].strip()
                    block_number = row[3].strip()
                    
                    # 新增 hash 列，填充空字符串（表示未知）
                    tx_hash = ''
                    
                    writer.writerow([start_id, end_id, value, tx_hash, block_number])
                    row_count += 1
            
            print(f"   ✅ 完成！共处理 {row_count} 行，输出文件: {USDT_TRANSFERS_OUTPUT}")
            
    except FileNotFoundError:
        print(f"   ❌ 错误：找不到文件 {USDT_TRANSFERS_INPUT}，请检查路径")
        sys.exit(1)
    except Exception as e:
        print(f"   ❌ 处理失败: {e}")
        sys.exit(1)


def fix_node_file(input_file, output_file):
    """
    修复节点文件：确保表头是 address:ID(Address)
    """
    print(f"\n📄 处理节点文件: {input_file}")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as infile, \
             open(output_file, 'w', encoding='utf-8', newline='') as outfile:
            
            reader = csv.reader(infile)
            writer = csv.writer(outfile)
            
            # 读取并修正表头
            header = next(reader)
            if header[0] != 'address:ID(Address)':
                print(f"   ⚠️ 表头 '{header[0]}' 修正为 'address:ID(Address)'")
                writer.writerow(['address:ID(Address)'])
            else:
                writer.writerow(header)
            
            # 复制数据行
            row_count = 0
            for row in reader:
                if row and row[0].strip():  # 跳过空行
                    writer.writerow([row[0].strip()])
                    row_count += 1
            
            print(f"   ✅ 完成！共处理 {row_count} 个地址，输出文件: {output_file}")
            
    except FileNotFoundError:
        print(f"   ⚠️ 文件 {input_file} 不存在，跳过")
    except Exception as e:
        print(f"   ❌ 处理失败: {e}")


def verify_csv_format(file_path, expected_header):
    """
    验证 CSV 文件的表头是否符合预期
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            if header == expected_header:
                print(f"   ✅ {file_path} 格式验证通过")
                return True
            else:
                print(f"   ⚠️ {file_path} 表头为: {header}")
                print(f"      预期表头: {expected_header}")
                return False
    except Exception as e:
        print(f"   ❌ 验证失败: {e}")
        return False


def main():
    print("=" * 60)
    print("🚀 开始统一 CSV 文件格式")
    print("=" * 60)
    
    # 1. 处理交易文件
    fix_transactions_file()
    fix_usdt_transfers_file()
    
    # 2. 处理节点文件
    for input_file, output_file in zip(NODES_INPUTS, NODES_OUTPUTS):
        fix_node_file(input_file, output_file)
    
    # 3. 验证输出文件
    print("\n" + "=" * 60)
    print("🔍 验证输出文件格式")
    print("=" * 60)
    
    verify_csv_format(
        TRANSACTIONS_OUTPUT,
        [':START_ID(Address)', ':END_ID(Address)', 'value:string', 'hash', 'block_number:int']
    )
    verify_csv_format(
        USDT_TRANSFERS_OUTPUT,
        [':START_ID(Address)', ':END_ID(Address)', 'value:string', 'hash', 'block_number:int']
    )
    
    print("\n" + "=" * 60)
    print("✅ 所有文件处理完成！")
    print("📌 请使用以下文件进行 neo4j-admin import:")
    print(f"   - 节点: {NODES_OUTPUTS[0]}, {NODES_OUTPUTS[1]}")
    print(f"   - 关系: {TRANSACTIONS_OUTPUT}, {USDT_TRANSFERS_OUTPUT}")
    print("=" * 60)


if __name__ == "__main__":
    main()
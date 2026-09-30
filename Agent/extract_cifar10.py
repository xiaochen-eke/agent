import os
import sys
import pickle
from PIL import Image

def load_batch(path):
    with open(path, 'rb') as f:
        d = pickle.load(f, encoding='bytes')
    # Keys are b'data', b'labels' or b'fine_labels'
    data = d.get(b'data')
    labels = d.get(b'labels') or d.get(b'fine_labels')0
    return data, labels

def save_images_from_batch(batch_path, out_dir, prefix, label_names=None):
    data, labels = load_batch(batch_path)
    os.makedirs(out_dir, exist_ok=True)
    n = len(labels)
    # data shape: (N, 3072) as R(1024),G(1024),B(1024)
    for i in range(n):
        arr = data[i]
        r = arr[0:1024].reshape(32,32)
        g = arr[1024:2048].reshape(32,32)
        b = arr[2048:3072].reshape(32,32)
        img = Image.merge('RGB', [Image.fromarray(r.astype('uint8')), Image.fromarray(g.astype('uint8')), Image.fromarray(b.astype('uint8'))])
        label = labels[i]
        label_name = label_names[label] if label_names and label < len(label_names) else str(label)
        fname = f"{prefix}_{i}_label{label}_{label_name}.jpg"
        img.save(os.path.join(out_dir, fname))

def load_label_names(meta_path):
    if not os.path.exists(meta_path):
        return None
    with open(meta_path, 'rb') as f:
        meta = pickle.load(f, encoding='bytes')
    names = meta.get(b'label_names') or meta.get(b'fine_label_names')
    if names:
        return [n.decode('utf-8') for n in names]
    return None

def main():
    if len(sys.argv) < 3:
        print('用法: python extract_cifar10.py <cifar_batch_dir> <out_dir>')
        sys.exit(1)

    batch_dir = sys.argv[1]
    out_dir = sys.argv[2]

    if not os.path.exists(batch_dir):
        print(f'错误：找不到文件夹 {batch_dir}')
        sys.exit(1)

    label_names = None
    meta_path = os.path.join(batch_dir, 'batches.meta')
    if os.path.exists(meta_path):
        label_names = load_label_names(meta_path)

    files = sorted([f for f in os.listdir(batch_dir) if os.path.isfile(os.path.join(batch_dir, f)) and f.startswith('data_batch') or f == 'test_batch'])
    if not files:
        # maybe files named differently
        files = [f for f in os.listdir(batch_dir) if f.endswith('.p') or f.endswith('.pickle')]

    total = 0
    for fname in files:
        full = os.path.join(batch_dir, fname)
        prefix = os.path.splitext(fname)[0]
        out_sub = os.path.join(out_dir, prefix)
        print(f'处理 {full} -> {out_sub}')
        save_images_from_batch(full, out_sub, prefix, label_names)
        total += 1

    print(f'完成：处理 {total} 个批次，图片输出至 {out_dir}')

if __name__ == '__main__':
    main()

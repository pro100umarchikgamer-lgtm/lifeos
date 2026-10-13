"""Streaming authenticated backup encryption; no record is deleted or uploaded."""
import argparse
import hashlib
import os
import struct
import sys
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC=b'LIFEOSB1'
BLOCK=1024*1024

def key(password,salt):
    if len(password)<32:raise ValueError('Backup key must contain at least 32 bytes')
    return Scrypt(salt=salt,length=32,n=2**15,r=8,p=1).derive(password)

def encrypt(source,target,password):
    salt=os.urandom(16);nonce=os.urandom(12);header=MAGIC+salt+nonce
    cipher=Cipher(algorithms.AES(key(password,salt)),modes.GCM(nonce)).encryptor()
    cipher.authenticate_additional_data(header);target.write(header)
    while chunk:=source.read(BLOCK):target.write(cipher.update(chunk))
    target.write(cipher.finalize());target.write(cipher.tag)

def decrypt(source,target,password):
    header=source.read(36)
    if len(header)!=36 or header[:8]!=MAGIC:raise ValueError('Invalid backup header')
    source.seek(0,2);size=source.tell();source.seek(size-16);tag=source.read(16);source.seek(36)
    cipher=Cipher(algorithms.AES(key(password,header[8:24])),modes.GCM(header[24:36],tag)).decryptor()
    cipher.authenticate_additional_data(header);remaining=size-52
    if remaining<0:raise ValueError('Truncated backup')
    while remaining:
        chunk=source.read(min(BLOCK,remaining))
        if not chunk:raise ValueError('Truncated backup')
        remaining-=len(chunk);target.write(cipher.update(chunk))
    target.write(cipher.finalize())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['encrypt','decrypt']);parser.add_argument('--key-file',required=True);parser.add_argument('--input')
    args=parser.parse_args();password=Path(args.key_file).read_bytes()
    if args.mode=='encrypt':encrypt(sys.stdin.buffer,sys.stdout.buffer,password)
    else:
        if not args.input:raise SystemExit('--input is required for authenticated seekable decryption')
        with Path(args.input).open('rb') as source:decrypt(source,sys.stdout.buffer,password)

if __name__=='__main__':main()

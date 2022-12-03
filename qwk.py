import sys
import argparse
import zipfile
import struct

parser = argparse.ArgumentParser()

parser.add_argument('file1', help='the messages.dat filename, or the QWK packet', nargs='?', default='messages.dat')
parser.add_argument('file2', help='the output filename. default is console', nargs='?')
parser.add_argument('-v', '--verbose', help='verbose output. export message id fields that may not be relevant', action='store_true')
parser.add_argument('-p', '--private', help='export messages marked private', action='store_true')

args = parser.parse_args()

verbose=args.verbose
exportPrivate=args.private

with open (args.file1, 'rb') as f:
    header=f.read(2)

if header ==b"PK":
    with zipfile.ZipFile(args.file1) as myzip:
        with myzip.open('messages.dat') as f:
            data=bytearray(f.read())
else:
    with open (args.file1, 'rb') as f:
        data=bytearray(f.read())
        
intBlocks=0
fullmessagebuffer=''

for i in range(0, len(data), 128):
    record=data[i:i+128]
    if i==0:
        if record[0:9]!=b'Produced ':
            sys.exit('not a messages.dat file')
        continue
    if intBlocks==0:
        messagebuffer='--------------------------------------------------------------------------------\r\n'
        status, msgnum, msgdate, msgtime, msgto, msgfrom, msgsubject, msgpassword, refnum, numblocks, msgflag, confnum, lognum, nettag = struct.unpack('<c7s8s5s25s25s25s12s8s6scHHc', record)
        #print(status, msgnum, msgdate, msgtime, msgto, msgfrom, msgsubject, msgpassword, refnum, numblocks, msgflag, confnum, lognum, nettag)
        messageType=status.decode('latin1')
        isPassword=False
        isPrivate=True
        if messageType in ['+', '*', '~', '`']:
            pass
        elif messageType in ['%', '^', '!', '#', '$']:
            isPassword=True
        elif messageType in [' ', '-']:
            isPrivate=False
        else:
            sys.exit('invalid message type. corrupt?')
        if verbose==True:
            messagebuffer+=('Message number: '+msgnum.decode('latin1')+'                                     ')
        messagebuffer+=('Date: '+msgdate.decode('latin1')+' '+msgtime.decode('latin1')+'\r\n')
        messagebuffer+=('From: '+msgfrom.decode('latin1')+'\r\n')
        messagebuffer+=('To: '+msgto.decode('latin1')+'\r\n')
        messagebuffer+=('Subject: '+msgsubject.decode('latin1')+'\r\n')
        if verbose==True:
            messagebuffer+=('Reference number: '+refnum.decode('latin1')+'                                  ')
            messagebuffer+=('Conference number: '+str(confnum)+'\r\n')
        messagebuffer+='\r\n'
        tempblocks=numblocks.decode('latin1').strip()
        intBlocks=int(tempblocks)-1
    else:
        temprecord=record.decode('latin1').replace('\xe3','\r\n')
        if intBlocks==1:
            temprecord=temprecord.rstrip()+'\r\n'
        messagebuffer+=temprecord
        intBlocks=intBlocks-1
        if intBlocks==0:
            if (exportPrivate==True or isPrivate==False) and isPassword==False:
                 fullmessagebuffer+=messagebuffer

if args.file2 ==None:
    print (fullmessagebuffer)
else:
    with open (args.file2, 'w', encoding='latin1') as f:
        f.write(fullmessagebuffer)

        
        


            
  


import sys
import argparse

parser = argparse.ArgumentParser()

parser.add_argument('file1', help='the messages.dat filename', nargs='?', default='messages.dat')
parser.add_argument('file2', help='the output filename. default is console', nargs='?')
parser.add_argument('-v', '--verbose', help='verbose output. export message id fields that may not be relevant', action='store_true')
parser.add_argument('-p', '--private', help='export messages marked private', action='store_true')

args = parser.parse_args()

verbose=args.verbose
exportPrivate=args.private

with open (args.file1, 'rb') as f:
    data=bytearray(f.read())

intBlocks=0
fullmessagebuffer=''

for i in range(0, len(data), 128):
    record=data[i:i+128].decode('latin1')
    if i==0:
        if record[0:9]!='Produced ':
            sys.exit('not a messages.dat file')
        continue
    if intBlocks==0:
        messagebuffer='--------------------------------------------------------------------------------\r\n'
        messageType=record[:1]
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
            messagebuffer+=('Message number: '+record[1:6]+'                              ')
        messagebuffer+=('Date: '+record[8:16]+' '+record[16:21]+'\r\n')
        messagebuffer+=('From: '+record[46:71]+'\r\n')
        messagebuffer+=('To: '+record[21:46]+'\r\n')
        messagebuffer+=('Subject: '+record[71:96]+'\r\n')
        if verbose==True:
            messagebuffer+=('Reference number: '+record[108:116]+'\r\n')
        messagebuffer+='\r\n'
        intBlocks=int(record[116:122].strip())-1
    else:
        temprecord=record.replace('\xe3','\r\n')
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

        
        


            
  


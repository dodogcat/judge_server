def recvResult(p):
    return str(p.recvuntil(b"(gdb)"), 'utf-8')

def comment_remover(text):
    def replacer(match):
        s = match.group(0)
        if s.startswith('/'):
            return " " # note: a space and not an empty string
        else:
            return s
    pattern = re.compile(
        r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
        re.DOTALL | re.MULTILINE
    )
    return re.sub(pattern, replacer, text)

def defaultSetting(name, p):
    file_name = name

    source = recvResult(p)
    print(source)

    p.sendline(bytes('file ' + file_name, 'utf-8'))
    print("send file " + file_name)
    source = recvResult(p)
    print(source)

    # # watch 여러개 걸기 위한 세팅 -> 이젠 안씀
    # p.sendline(b'set can-use-hw-watchpoints 0')
    # print("send set can-use-hw-watchpoints 0")
    # source = recvResult(p)
    # print(source)

    # # 잘 걸렸는지 확인
    # p.sendline(b'show can-use-hw-watchpoints')
    # print("send show can-use-hw-watchpoints")
    # source = recvResult(p)
    # print(source)

    # 색깔 나오는거 없애기
    p.sendline(b'set style enabled off')
    print("send set style enabled off")
    source = recvResult(p)
    print(source)

    # 잘 됐는지 확인용
    p.sendline(b'show style enabled')
    print("send show style enabled")
    source = recvResult(p)
    print(source)
    return p

def makeTempFile(file):
    f = open(file, 'r')
    data = f.read()
    data = comment_remover(data)
    f2 = open(file[0:-2] + "_temp.c", 'w')
    f2.write(data)
    f2.close()
    f.close()

def printfAddBufferout(file):
    f = open(file, 'r')
    data = []
    while True:
        line = f.readline()
        if not line:
            break
        data.append(line)
        if "printf" in line:
            data.append('printf("\\n");\n')
    f.close()

    clang = ""
    for i in data:
        clang += i

    f = open(file, 'w')
    f.write(clang)
    f.close()
    
def findGlobal(file):
    f = open(file, 'r')
    tpList = []
    nmList = []

    while True:
        row = f.readline()
        if not row:
            break
        if row[0] == '\t' or row[0] == '#' or row[0] == '{' or row[0] == '}' or row[0] == '\n': 
            continue
        if "(" in row or "typedef" in row or not(";" in row):
            continue

        ls = row.split('\t')

        varType = ls[0].split(' ')
        if len(varType) == 1:
            varType = varType[0]
        if len(varType) == 2:
            varType = varType[1]
        
        
        varName = ls[-1][0:-2].split(" = ")[0]

        tpList.append(varType)
        nmList.append(varName)
        # print(varType + "\t" + varName)

    f.close()

    return tpList, nmList

def setWatch(p):
    p.sendline(b'info locals')
    source = recvResult(p)
    # print(source)

    data = source.split('\n')

    local = []
    for row in data:
        var = rmColor(row).split(" = ")[0]
        var = var.replace(' ','')
        if "(gdb)" in var:
            continue
        local.append(var)

        # 바뀔때마다 감지하면 scanf 에서 고장남
        # p.sendline(bytes("watch " + var, 'utf-8'))
        # print("send watch " + var)
        # source = recvResult(p)
        # print(source)
            
    local = list(filter(None, local))
    # return []
    return local

def rmColor(text):
    text = text.replace("\x1b[36m", '')
    text = text.replace("\x1b[m", '')
    text = text.replace("\x1b[34m", '')
    text = text.replace("\x1b[33m", '')

    return text

def checkLocals(p, variables, frame):
    values = []
    
    for var in variables:
        # 주소 가져오기
        p.sendline(bytes("p &" + var, 'utf-8'))
        # print("send p &" + var)
        source = recvResult(p)
        if "Cannot" in source:
            source = "* = ERROR123456"
        source = rmColor(source)
        fEqual = source.find('=')
        source = source[fEqual + 2: -6]
        # print("&" + var + " = " + source)
        values.append(["&" + var,source])

        # 값 가져오기
        p.sendline(bytes("p " + var, 'utf-8'))
        # print("send p " + var)
        source = recvResult(p)
        if "Cannot" in source:
            source = "* = ERROR123456"
        source = rmColor(source)
        fEqual = source.find('=')
        source = source[fEqual + 2: -6]
        # print(var + " = " + source)
        values.append([var,source])

    # if currentFunc == "DFS" or currentFunc == "createVertex":
        # print("for break")

    # 포인터들 따라 들어가보자.
    for var in values:
        # 주소값패스
        if var[0][0] == '&':
            continue
        # 포인터 같아 보이면 추가
        if var[1][0] == '(':
            p.sendline(bytes("p *" + var[0], 'utf-8'))
            # print("send p *" + var[0])
            source = recvResult(p)
            if "Cannot" in source:
                source = "* = ERROR123456"
            source = rmColor(source)
            fEqual = source.find('=')
            source = source[fEqual + 2: -6]
            # print("*" + "(" + var[0] + ")" + " = " + source)
            values.append(["*" + "(" + var[0] +  ")", source])
            continue
        # 배열은 = 없으니 없으면 패스? ㄴㄴ 그러면 포인터배열 꼬임
        # 구조체 같아 보이면 주소값만 따라가기
        if var[1][0] == '{':
            # 맴버마다 분리
            members = var[1][1:-1].split(", ")
            for member in members:
                if not(" = " in member):
                    continue
                member_name = member.split(" = ")[0]
                member_value = member.split(" = ")[1]
                # 개행 에러 잡기 ex)"*n8": "{left = 0xc483485824448b48, id = 1096637288, data = 1096630620, \n  right = 0x813d8b48c35f415e}",
                if member_name[0] == '\n':
                    member_name = member_name[3:]

                # 맴버중에서 값이 주소처럼 보이면 추가
                if("0x" in member_value):
                    # 무한 루프 방지책 node가 노드 가르키는거 대책용 순환 금지법
                    loop = False
                    for loopCheck in values:
                        if (member_value in loopCheck[1]) and (var[0] != loopCheck[0]):
                            loop = True
                            break
                    if loop == True:
                        continue

                    p.sendline(bytes("p " + "(" + var[0] + "->" + member_name + ")", 'utf-8'))
                    # print("send p " + "(" +  var[0] + "->" + member_name + ")")
                    source = recvResult(p)
                    if "Cannot" in source:
                        source = "* = ERROR123456"
                    source = rmColor(source)
                    fEqual = source.find('=')
                    source = source[fEqual + 2: -6]
                    # print("(" + var[0] + "->" + member_name + ")" + " = " + source)
                    values.append(["(" + var[0] + "->" + member_name + ")", source])
                    continue


    return values

def getFuncList(p, file):
    # 그냥 소스코드에서 가져오는게 더 빠를듯;;
    # 일단 주석처리
    p.sendline(b'info functions')

    while True:
        input = str(p.recvline(), 'utf-8')
        # print(input)
        if (file in input):
            break


    source = recvResult(p)
    
    findString = "File " + file + ":\n"
    startIdx = source.find(findString)
    source = source[startIdx:]
    endIdx = source.find("\n\n")
    source =  source[0:endIdx]

def getFuncBySourceCode(file):
    f = open(file, 'r')
    funcList = []
    while True:
        line = f.readline()
        if not line:
            break

        if line[0] == '\t':
            continue
        if not ("(" in line):
            continue

        exType = line.split('\t')[1]
        name = exType.split('(')[0]
        name = name.replace("*","")
        funcList.append(name)

    f.close()

    return funcList

def sendOrder(p, order:str):
    p.sendline(bytes(order, 'utf-8'))
    # print("send " + order)

def rmNumThenTab(line:str):
    cutted = ""

    rmDigit = True
    rmTab = True
    for i in range(len(line)):
        if((line[i].isdigit() == True) and (rmDigit == True)):
            continue
        if((line[i] == '\t') and (rmTab == True)):
            rmDigit = False
            continue
        rmDigit = False
        rmTab = False
        cutted += line[i]

    return cutted

def listToDict(index:int, info:list, output:list, currentFunc):
    diction = {}
    diction["step"] = index
    diction["var"] = {}
    for i in range(len(info) - 1):
        string = info[i][1]
        if string[0] == '\"':
            string = string[1:-1]
        else:
            # 일단 배열기준으로 갈라보자
            try:
                if string[0] == '{':
                    sppprit = string[1:-1].split(',')
                    for j in range(len(sppprit)):
                        sppprit[j] = sppprit[j].replace(' ', '')
                        sppprit[j] = int(sppprit[j])
                    diction["var"][info[i][0]] = sppprit
                    continue
                else:
                    string = int(string)

            except:
                string = string

        diction["var"][info[i][0]] = string

    if "(gdb)" in info[len(info) - 1][0]:    
        diction["next"] = info[len(info) - 1][0][:-6]
    else:   
        diction["next"] = info[len(info) - 1][0]

    if output:
        diction["output"] = output

    diction["frame"] = currentFunc

    return diction

def getLocals(p, afterPrintf=False):
    locals = []

    sendOrder(p, "info locals")
    result = recvResult(p)

    # print(result)

    result = result[1:]

    isArray = False
    var = ""
    for char in range(len(result)):
        if(result[char]== '{'):
            isArray = True  
        if(isArray == True and result[char] == '\n'):
            continue 
        if(isArray==True and result[char] == '}'):
            var += result[char]
            locals.append(var)
            var = ""
            isArray = False
            continue
        if(isArray==False and result[char] == '\n'):
            # var += result[char]
            locals.append(var)
            var = ""
            isArray = False
            continue

        var += result[char]
            
    
    locals = list(filter(None, locals))
    
    for row in range(len(locals)):
        locals[row] = locals[row].split(" = ")[0]

    return locals

def countNextline(s:str):
    # printf가 개행하는 것들만 찾음. 문자열에서 \n 찾는거 아님!
    # if s == "printf(\"%d\\n\", a);":
    #     print("A")
    count = 0
    for i in range(len(s) - 1):
        if s[i]=='\\' and s[i + 1]=='n':
            count+=1

    return count

def getFrame(p, func):
    sendOrder(p, "info frame")
    recv = recvResult(p)

    # 현재 프레임 찾기
    second = recv.split('\n')[1]
    for s in func:
        if s in second:
            return s

    return "ERROR"

def getArgs(p):
    sendOrder(p, "info frame")
    recv = recvResult(p)

    # 인자들 받아오기
    argStart = recv.find(", args: ") + 8
    argEnd = recv.find("\n Locals at ")
    ar = recv[argStart:argEnd]
    if ar == "":
        return []
        
    index = ar.find("\n")
    if index != -1:
        ar = ar.replace("\n    ", "")
    
    args = ar.split(", ")

    ret = []
    for i in range(len(args)):
        ret.append(args[i].split("=")[0])

    return ret

def getArraySizeFromNext(p, next:str):
    if not (")malloc(" in next and ");" in next):
        return 0
    
    malIndex = next.find("malloc")
    trimOrder = next[malIndex + 7:-2]
    nums = trimOrder.split(" * ")

    trueOrder = ""
    for num in nums:
        if not("sizeof" in num):
            trueOrder += num + "*"
    
    trueOrder=trueOrder[:-1]

    # sizeof 하나만 있는 경우
    if trueOrder == "":
        return 0

    sendOrder(p, "p " + trueOrder)
    result = recvResult(p)
    result = result.split(" = ")[1]
    result = int(result[:-6])
    
    return result

def breakAndRun(p):
    # 시작인 main에 브레이크 포인트 걸기
    p.sendline(b'b main')
    print("send b main")
    source = recvResult(p)
    print(source)
    
    # 시작하기
    p.sendline(b'r')
    print("send r")
    source = recvResult(p)
    print(source)
    last = source.split("\n")[-2]

    return last


import json
from pwn import *
import sys

# context.log_level = 'debug'
# name = b'doubleDimensionPointer'
# name = b'globalLocalSame'
# name = b'tree'
# name = b'bubbleSort'
# name = b'pointerArray'
# name = b'graphSearch'

name = bytes(sys.argv[1], "UTF-8")

print("input name: " + str(name))
file = str(name, 'utf-8') + ".c"
inputString = ["5 7 1",
"1 2",
"1 4",
"5 1",
"3 5",
"4 3",
"3 1",
"2 3",
]
inputCount = 0

makeTempFile(file)
file = file[0:-2] + "_temp.c"
out = file[0:-2]

# make printf("\n"); added file
printfAddBufferout(file)

# c code formatter
command = "python3 -m c_formatter_42 " + file
result = subprocess.run(command.split(' '), stdout=subprocess.PIPE, text=True)
print(result.stdout)

# 새로운 파일 컴파일
command = "gcc -g3 -o "+ out + " "+ file
# command = "gcc -g3 -O0 -o "+ out + " "+ file
result = subprocess.run(command.split(' '), stdout=subprocess.PIPE, text=True)
print(result.stdout)

# 함수들 추출
func = getFuncBySourceCode(file)
func = list(filter(None, func))

# 제어 시작
p = process('gdb')
defaultSetting(out, p)

source = breakAndRun(p)


# 참조할 변수 목록 얻기
variables = []
globalType, g_variables = findGlobal(file)
# 지역변수 추가
variables = g_variables + setWatch(p)
# 빈 리스트 제거
variables = list(filter(None, variables))

debugs = []

# JSON 파일 만들기 위한 데이터 담는 곳
forJson = {}

# 에러 막기 위한 처음 소스 지정
# source = "int main(){"

# 디버깅용
interactivalbe = False

# 
currentFunc = "main"
# 숫자로 정렬을 위해 "functions" 대신 -1 사용
forJson[-1] = func
numNextline = countNextline(rmNumThenTab(source))
steps = 0
dead = False
while(True):
    # 기본 함수들이면 n을 보내서 스킵하게 한다.
    if "scanf" in source or "printf" in source or "exit" in source or "malloc" in source:
        sendOrder(p, "n")
        
        if "scanf" in source:
            # p.interactive()
            sendOrder(p, inputString[inputCount])
            inputCount += 1
    else:
        sendOrder(p, "s")

    source = recvResult(p)
    source = rmColor(source)

    # watch 사용 안함
    # # 변수 값 추가
    # if "Old value" in source and "New value" in source:
    #     debugs.append(source[0:-6] + "----------------------\n")
    
    print(source)

    # 디버깅용
    # if interactivalbe == True:
    #     p.interactive()

    # 현재 함수 얻기
    currentFunc = getFrame(p, func)
    if currentFunc == "ERROR":
        print("FUCNK")
        break
    
    # 함수 인자들도 추적
    args = getArgs(p)
    # if args!="":
    #     print("a")

    args = list(filter(None, args))

    # 전역 + 지역 + 인자 == 변수들
    variables = g_variables + getLocals(p) + args
    # 이놈들 값 가져오기
    stepLocals = checkLocals(p, variables, currentFunc)

    # printf로 인한 출력 받기 위해 다듬기
    source = source[1:]
    prints = []
    if numNextline == 0:
        # 없으면 next만
        a = [ rmNumThenTab(source) ]
    else:
        # 있으면 나눠서 가져옴
        sppprit = source.split('\n')
        prints = sppprit[:-2]
        a = [rmNumThenTab(sppprit[-2])]
    # next 부분 추가
    stepLocals.append(a)
    # debugs.append(stepLocals)

    # 구조 모양 만들면서 next output frame 추가
    forJson[(steps)] = listToDict(steps, stepLocals, prints, currentFunc)

    # 다음에 print 있는지 확인
    numNextline = countNextline(forJson[(steps)]["next"])
    if numNextline !=0 :
        print("print on gdb!!!")

    # 다음에 malloc 있으면 배열 크기 확인 배열
    # 확인 후 배열 아니면 그냥 무시
    arrSize = getArraySizeFromNext(p, forJson[(steps)]["next"])
    if(arrSize > 1):
        # 배열이면 변수 목록에 추가 필요... 글로벌에 추가하자
        # 선언하자마자 동적할당은 생각하지 않는걸로...
        # 막아야 한다면 C언어 소스단에서 수정하게 하자
        
        # 변수 가져오기
        arrayVar = forJson[(steps)]["next"].split(" = ")[0]
        # 변수 주소 가져옴
        sendOrder(p, "p &" + arrayVar)
        arrayVarDirect = recvResult(p).split(" = ")[1][:-6]

        # next빼고 돌면서 어떤 놈이 배열인지 찾음
        for i in range(len(stepLocals) - 1):
            if stepLocals[i][1] == arrayVarDirect:
                arrayVar = stepLocals[i][0][1:]
                break

        # 전역변수에 배열들 추가
        for i in range(arrSize):
            g_variables.append(arrayVar + "[" + str(i) + "]")

    # 한번 칸씩 움직이는 단위가 스탭!
    steps+=1

    # # 디버깅용
    # print("----------------------------------")
    # print("steps: " + str(steps))
    # print("frame: " + currentFunc)
    # print("----------------------------------")

    # main 끝나면 잡다한거 나오기 전에 종료
    # 근데 태욱이도 return 안씀;;
    if dead == True:
        break

    if "return" in source:
        # print("end func")
        if currentFunc == "main":
            # 다음 턴에 사망하게 하자
            dead = True
            # break

    # 혹시 모를 끝났는지 확인
    if "The program is not being run." in source:
        break


with open('result_'+file[0:-2]+'.json','w') as f:
    json.dump(forJson,f,indent=4, sort_keys=True)
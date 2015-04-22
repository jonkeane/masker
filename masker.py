from __future__ import division
import os, subprocess, csv, shutil, re
import pyelan.pyelan as pyelan

def readData(file="RobinTest.csv"):
    f = open(file, 'r')
    data = csv.DictReader(f)

    dataOut = {} #Initialize emptry dictionary
    for data in data:
        wordInstance = data["wordInstanceVideoPath"]
        wordInstance = os.path.basename(wordInstance)
        try:
            dataOut[wordInstance].append(data)
        except KeyError:
            dataOut[wordInstance] = [data]

    return dataOut

def chunks(l, n):
    """chunks a list into chunks of n length"""
    return [l[i:i+n] for i in range(0, len(l), n)]

def transitionParser(data):
    """Parses out only the transitions from a set of apogees given in data"""
    dataOut = {}
    for instance in data:
        wordBegin = int(data[instance][1]["wordBegin"])
        wordEnd = int(data[instance][1]["wordEnd"])
        timePoints = []
        for apogee in data[instance]:
            timePoints.append(int(apogee['beginTime']))
            timePoints.append(int(apogee['endTime']))
        timePoints[:] = [x - wordBegin for x in timePoints]
        timePoints = sorted(timePoints)[1:-1]
        transitions = chunks(timePoints, 2)

        dataOut[instance] = ((wordBegin, wordEnd) ,transitions)
    return dataOut

def holdParser(data):
    """Parses out only the holds from a set of apogees given in data"""
    dataOut = {}
    for instance in data:
        wordBegin = int(data[instance][1]["wordBegin"])
        wordEnd = int(data[instance][1]["wordEnd"])
        timePoints = []
        for apogee in data[instance]:
            timePoints.append(int(apogee['beginTime']))
            timePoints.append(int(apogee['endTime']))
        timePoints[:] = [x - wordBegin for x in timePoints]
        timePoints = sorted(timePoints)
        holds = chunks(timePoints, 2)

        dataOut[instance] = ((wordBegin, wordEnd) ,holds)
    return dataOut

def timeSpanFrameChanger(data, frames=1, shrink=False, fps=60000/1001.):
    """take a list of two, and adjusts the times by adding or subtracting frames on either side."""
    sign = frames
    if shrink == True:
        sign = sign*-1
    out = []
    out.append(int(round(data[0] - sign*(1/fps)*1000)))
    out.append(int(round(data[1] + sign*(1/fps)*1000)))
    return out

def timeSpanPercentageChanger(data, perc=0.5, shrink=True, fps=6000/1001.):
    """take a list of two, and adjusts the times by adding or subtracting a percentage on either side."""
    sign = 1
    if shrink == True:
        sign = sign*-1
    delta = data[1]-data[0]
    out = []
    out.append(int(round(data[0] - sign*(1-perc)*delta/2.)))
    out.append(int(round(data[1] + sign*(1-perc)*delta/2.)))
    return out

def spanChecker(data):
    """Check to make sure the spans given are well formed"""
    out = []
    for span in data:
        begin = span[0]
        end = span[1]
        # make sure no spans are before the beginning of the clip
        if begin < 0:
            begin = 0
        if end < 0:
            end = 0
        # make sure that no spans are negative
        if end-begin > 0:
            out.append([begin, end])
    return out

def noMasker(videoIn, outpath, slowDown=2,  maskImage="masker/masks/black852x480.jpg"):
    output = subprocess.check_output(["ffmpeg", "-i", "originalVideos/"+videoIn, "-q:v", "0", "-an", "-vf", "setpts="+str(slowDown)+"*PTS", "-r", "29.97", "-y", outpath])#,  stderr=subprocess.STDOUT, stdout = subprocess.PIPE, bufsize=1, universal_newlines=True)


def masker(videoIn, wordDur, masks, outpath, slowDown=2, maskImage="masker/masks/black852x480.jpg"):
    if os.path.exists("tmp"):
        shutil.rmtree("tmp")
    os.makedirs("tmp")

    # change the spans
    print(masks)
    # masks = [timeSpanPercentageChanger(x, perc=0.75, shrink=True) for x in masks]
    masks = [timeSpanFrameChanger(x, frames=0, shrink=True) for x in masks]
    masks = spanChecker(masks)
    print(masks)
    # flatten the masks list
    nonMasks = [item for sublist in masks for item in sublist]
    nonMasks.append(0)
    nonMasks.append(wordDur[1]-wordDur[0])
    nonMasks = sorted(nonMasks)
    nonMasks = chunks(nonMasks, 2)
    print(nonMasks)

    # remove the last nonMask, if it is less than a frame:
    if nonMasks[-1][1]-nonMasks[-1][0]<16.68:
        print("deleted the last nonMask because it was less than one frame.")
        del nonMasks[-1]
        print(nonMasks)

    # make mask pipes
    maskFiles = []
    for mask in range(0,len(masks)):
        file = "tmp/mask"+str(mask)+".mpg"
        os.mkfifo(file)
        maskFiles.append(file)

    # make non mask pipes
    nonMaskFiles = []
    for nonMask in range(0,len(nonMasks)):
        file = "tmp/"+str(nonMask)+".mpg"
        os.mkfifo(file)
        nonMaskFiles.append(file)


    subprocs = []
    # iterate over the masks and maskFiles starting process
    for mask, maskFile in zip(masks, maskFiles):
        cmd = ["ffmpeg", "-f", "image2", "-loop", "1", "-r:v", "59.94", "-i", maskImage, "-pix_fmt", "yuv420p", "-an", "-t", str((mask[1]-mask[0])/1000.), "-y", maskFile]
        print(cmd)
        subprocs.append(subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout = subprocess.PIPE, bufsize=1, universal_newlines=True))
    # iterate over the nonMasks and nonMaskFiles starting process
    for nonMask, nonMaskFile in zip(nonMasks, nonMaskFiles):
        cmd = ["ffmpeg", "-i", "originalVideos/"+videoIn, "-ss", str(nonMask[0]/1000.), "-t", str((nonMask[1]-nonMask[0])/1000.), "-q:v", "0", "-y", nonMaskFile]
        print(cmd)
        subprocs.append(subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout = subprocess.PIPE, bufsize=1, universal_newlines=True))

    # catCmd = ["cat"]
    # add the first (non masked) segment
    # catCmd.extend([nonMaskFiles[0]])
    # add the rest of the segments interleaved
    # catCmd.extend([y for x in zip(maskFiles,nonMaskFiles[1:]) for y in x])
    # print(catCmd)
    #
    # ct = subprocess.Popen(catCmd, stdout=subprocess.PIPE)

    # output = subprocess.check_output(["ffmpeg", "-i", "-", "-q:v", "0", "-an", "-vf", "setpts=2*PTS", "-r", "29.97", "-y", outdir+"/"+"stim"+videoIn], stdin = ct.stdout)#,  stderr=subprocess.STDOUT, stdout = subprocess.PIPE, bufsize=1,
    ffmpegCatCmd = ['ffmpeg']
    # add the first (non masked) segment
    ffmpegCatCmd.extend(['-i', nonMaskFiles[0]])
    # add the rest of the segments interleaved
    interleaved = [y for x in
    zip(
    zip(['-i']*len(maskFiles), maskFiles),
    zip(['-i']*len(nonMaskFiles), nonMaskFiles[1:])
    ) for y in x]
    #flatten the list of tuples
    interleaved = [e for l in interleaved for e in l]
    ffmpegCatCmd.extend(interleaved)
    #count the number of inputs to get the number of videos being concated
    numVids = sum([x == '-i' for x in ffmpegCatCmd])

    streams = ''
    for n in range(0,numVids):
        streams += '['+str(n)+':0] '

    filters = streams+'concat=n='+str(numVids)+':v=1, setpts=+'+str(slowDown)+'*PTS [v]'
    ffmpegCatCmd.extend(['-filter_complex', filters, '-map', "[v]", '-q:v', '0', '-an', '-r', '29.97', '-y', outpath])

    print(ffmpegCatCmd)
    output = subprocess.check_output(ffmpegCatCmd, universal_newlines=True)#,  stderr=subprocess.STDOUT, stdout = subprocess.PIPE, bufsize=1,

    # works
    # output = subprocess.check_output(' '.join(ffmpegCatCmd), shell=True)#,  stderr=subprocess.STDOUT, stdout = subprocess.PIPE, bufsize=1,


    shutil.rmtree("tmp")


def parser(data):
    """Parses out only the holds from a set of apogees given in data"""
    dataOut = {}
    for instance in data:
        wordBegin = int(data[instance][1]["wordBegin"])
        wordEnd = int(data[instance][1]["wordEnd"])
        timePoints = []
        for apogee in data[instance]:
            timePoints.append(int(apogee['beginTime']))
            timePoints.append(int(apogee['endTime']))

        timePoints[:] = [x - wordBegin for x in timePoints]
        timePoints = sorted(timePoints)
        holds = chunks(timePoints, 2)

        timePoints = sorted(timePoints)[1:-1]
        transitions = chunks(timePoints, 2)


        word = data[instance][1]["word"]
        dataOut[instance] = ((wordBegin, wordEnd), word, holds, transitions)
    return dataOut


def processor(dataIn, outdir, maskImage="masker/masks/green852x480.jpg"):
    for videoIn in dataIn:
        print(videoIn)
        print(dataIn[videoIn])

        holdsMaskedfile = os.path.join(outdir,'transOnly','stim'+videoIn)
        masker(videoIn, wordDur=dataIn[videoIn][0], masks=dataIn[videoIn][3], outpath=holdsMaskedfile, slowDown=2, maskImage=maskImage)

        transMaskedfile = os.path.join(outdir,'holdsOnly','stim'+videoIn)
        masker(videoIn, wordDur=dataIn[videoIn][0], masks=dataIn[videoIn][3], outpath=transMaskedfile, slowDown=2, maskImage=maskImage)

        clearfile = os.path.join(outdir,'allClear','stim'+videoIn)
        noMasker(videoIn, outpath=clearfile, slowDown=2, maskImage=maskImage)


        saveDir = os.path.join(outdir, "elanFiles")
        basename = videoIn
        media = [clearfile, holdsMaskedfile, transMaskedfile]

        allTiers = pyelan.tierSet(media=media, tiers=[pyelan.tier("default", [pyelan.annotation(begin=1, end=2, value="foo")])])

        elanOut = os.path.join(saveDir,'.'.join([basename,"eaf"]))

        out = pyelan.tierSet.elanOut(allTiers, dest=elanOut)

        out.write(elanOut)





d = readData(file = "ritaApogeesCleaned.csv")
# trans = transitionParser(d)
# masker(trans, outdir="green0/greenTransOnly", maskImage="masker/masks/green852x480.jpg")
#
# holds = holdParser(d)
# masker(holds, outdir="green0/greenHoldsOnly", maskImage="masker/masks/green852x480.jpg")
#
#
# noMasker(trans, outdir="green0/nomask")

words = parser(d)

processor({"730.mp4": words["730.mp4"]}, outdir="test", maskImage="masker/masks/green852x480.jpg")

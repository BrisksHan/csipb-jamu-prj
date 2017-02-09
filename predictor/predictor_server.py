#!/usr/bin/python
import numpy as np
import signal
import socket
import time
import sys
import psycopg2

from config import database as db
from config import predictor_channel as ch
from config import MAX_ELAPSED_TIME
import blmnii
import util

connDB = psycopg2.connect(database=db['name'],user=db['user'],password=db['passwd'],
                      host=db['host'],port=db['port'])
cur = connDB.cursor()

def signal_handler(signal, frame):
    sys.stderr.write("Closing socket and database ...\n")
    sock.close()
    connDB.close()
    sys.exit(0)

def makeKernel(dataList,mode):
    dataList = list(set(dataList))
    dataDict = {e:i for i,e in enumerate(dataList)}#for Index
    simMat = np.zeros((len(dataList),len(dataList)), dtype=float)
    if mode=="com":
        qParam = ["com_id","com_similarity_simcomp","compound"]
    elif mode=="pro":
        qParam = ["pro_id","pro_similarity_smithwaterman","protein"]

    query = "SELECT " + qParam[0] +", " + qParam[1]+ " FROM " + qParam[2]
    queryC = " WHERE "

    for i,d in enumerate(dataList):
        if i>0:
            queryC += " OR "
        queryC += (qParam[0] + " = " + "'" + d + "'")
    query += queryC
    cur.execute(query)
    dataRows = cur.fetchall()
    for i,row in enumerate(dataRows):
        if row[1] != None:
            temp = row[1].split(',')
            temp = [i.split('=') for i in temp]
            for j in temp:
                if j[0].split(':')[0] in dataDict:
                    simMat[dataDict[row[0]]][dataDict[j[0].split(':')[0] ]]=float(j[1])

    return dataDict, simMat

def predict(queryString):
    maxIter = None
    pairIdList = None
    pairQueryList = None

    compList = None
    compMeta = None
    compSimMat = None
    protList = None
    protMeta = None
    protSimMat = None
    adjMat = None

    query = ""
    queryC = ""
    queryP = ""
    rows = None

    resPred = None
    sendRes = ""
    timeEx = time.time()

    sys.stderr.write ("Processing Query.... \n")
    pairQuery = [queryString.split(":")]

    ##Parsing to pair id list
    pairIdList = util.randData(pairQuery,1000)

    ############# Make simMat and dict #############
    sys.stderr.write ("Making kernel....\n")
    compList = [i[0] for i in pairIdList]
    compMeta, compSimMat = makeKernel(compList,"com")

    protList = [i[1] for i in pairIdList]
    protMeta, protSimMat = makeKernel(protList,"pro")

    ############# Make adjacency list #############
    sys.stderr.write ("Building connectivity data...\n")
    adjMat = np.zeros((len(compMeta), len(protMeta)), dtype=int)

    query = "SELECT com_id, pro_id, weight FROM compound_vs_protein"
    queryC = " WHERE ("
    for i,j in enumerate(compMeta):
        if i>0:
            queryC += " OR "
        queryC += " com_id = " + "'"+j+"'"
    queryC += ")"
    queryP = " AND ("
    for i,j in enumerate(protMeta):
        if i>0:
            queryP += " OR "
        queryP += " pro_id = " + "'"+j+"'"
    queryP += ")"

    query += queryC + queryP
    cur.execute(query)

    rows = cur.fetchall()
    for row in rows:
        adjMat[compMeta[row[0]]][protMeta[row[1]]]=(row[2])

    ########### Prediction ###################
    sys.stderr.write ("Running BLM-NII...\n")
    #Transform from PairId to PairIndex
    pairIndexList = [[compMeta[i[0]],protMeta[i[1]]] for i in pairIdList]

    resPred = blmnii.predict(adjMat,compSimMat,protSimMat,pairIndexList[0][0],pairIndexList[0][1])
    sendRes += pairIdList[0][0]+'|'+pairIdList[0][1]+'|'+str(resPred)
    sendRes += "|blm-nii-svm|"+'%s.%04f' % (time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(int(timeEx))), timeEx-int(timeEx))

    ############## push to DB ##################
    query = ""
    query1 = ""
    query2 = ""
    query3 = ""
    queryCheck = ""
    #
    sys.stderr.write ("Push data to DB...\n")
    ## Check row in the table ##
    queryCheck = "SELECT * FROM compound_vs_protein WHERE "
    queryCheck += "com_id='"+pairIdList[0][0]+"' AND pro_id='"+pairIdList[0][1]+"'"
    queryCheck += " AND source = 'blm-nii-svm'"
    cur.execute(queryCheck)
    dataRows = cur.fetchall()
    # ## Update row if data is already exsist on table ##
    if len(dataRows)>0:
        query1 = "UPDATE compound_vs_protein "
        query2 = "SET source='blm-nii-svm', weight="+ str(resPred)+", time_stamp=now() "
        query3 = "WHERE com_id='" + pairIdList[0][0] + "'AND pro_id='" + pairIdList[0][1]+"'"

    # ## Insert if no record found ##
    else:
        #May use INSERT INTO .. VALUE ... ON DUPLICATE KEY UPDATE
        query1 = "INSERT INTO compound_vs_protein (com_id, pro_id, source, weight) "
        query2 = "VALUES ( "+ "'" + pairIdList[0][0] + "', "+ "'" + pairIdList[0][1]
        query3 = "', " + "'blm-nii-svm', "+ str(resPred)+" )"

    query = query1 + query2 + query3
    sys.stderr.write(query+"\n")
    cur.execute(query)
    connDB.commit()

    return sendRes

if __name__ == '__main__':
    dataTemp= ""
    message = ""

    ##### Socket Part #####
    server_addr = (ch['host'],ch['port'])
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(server_addr)
    sys.stderr.write("Starting up server...\n")

    sock.listen(1)
    while True:
        sys.stderr.write("##################################################\n")
        sys.stderr.write("Waiting for connection...\n")
        signal.signal(signal.SIGINT, signal_handler)
        conn, addr = sock.accept()
        try:
            print >>sys.stderr, 'Connection from', addr
            while True:
                dataTemp = conn.recv(1024)
                print >>sys.stderr, 'Received "%s"' % dataTemp
                message += dataTemp

                if message[-3:]=="end":
                    sys.stderr.write ("Fetching Data Finished....\n")
                    message = message.split("|")[0]
                    break
        finally:
            predictResult = ""
            queryPair = message.split(",")
            start_time = time.time()
            for i,query in enumerate(queryPair):
                print time.time()-start_time
                if (i>0):
                    predictResult += ","
                if time.time()-start_time  <= MAX_ELAPSED_TIME:
                    predictResult += predict(query)
                else:
                    predictResult += query.split(":")[0]+"|"+query.split(":")[1]
                    predictResult += "|Null|Null|Null"
            conn.sendall(predictResult)
            conn.close()

            message = ""
            dataTemp= ""

    connDB.close()
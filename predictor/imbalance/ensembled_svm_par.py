# ensembled_svm.py
import os
import pickle
import numpy as np
from collections import Counter
from sklearn.model_selection import StratifiedKFold
from sklearn.model_selection import KFold
from sklearn import svm
from scoop import futures as fu
from scoop import shared as sh

class EnsembledSVM:
    def __init__(self,imaxTrSamples,imaxTeSamples,ibootstrap,isimDict,imsg):
        self._maxTrainingSamples = imaxTrSamples
        self._maxTestingSamples = imaxTeSamples
        self._boostrap = ibootstrap
        self._simDict = isimDict
        self._msg = imsg

    def fit(self,ixtr,iytr):
        xyTrList = self._divideSamples(ixtr,iytr,self._maxTrainingSamples)
        self._svmList = list( fu.map(self._fit2,
                                     [xytr[0] for xytr in xyTrList],
                                     [xytr[1] for xytr in xyTrList]) )

    def predict(self,ixte,mode):
        sh.setConst(mode=mode)
        sh.setConst(svmList=self._svmList)
        xTeList = self._divideSamples(ixte,None,self._maxTestingSamples)
        ypredList = list( fu.map(self._predict2,[i[0] for i in xTeList]) )

        ypred = [];
        for i in ypredList: ypred += i
        assert len(ypred)==len(ixte),str(len(ypred))+'!='+str(len(ixte))
        return ypred

    def writeSVM(self,outDir):
        fpath = os.path.join(outDir,'esvm.pkl')
        with open(fpath,'w') as f: pickle.dump(self._svmList,f)

    def _predict2(self,xte):
        svmList = sh.getConst('svmList')
        ypred2 = list( fu.map(self._predict3,svmList,[xte]*len(svmList)) )

        # ypred2 = [] # from all classifiers
        # for clf,xtr in svmList:
        #     simMatTe = self._makeKernel(xte,xtr)
        #     ypred2i = clf.predict(simMatTe) # remember: ypred2i is a vector
        #     ypred2.append(ypred2i)

        ypred3 = [] # ypred merged from all classifier
        mode = sh.getConst('mode')
        for i in range(len(xte)):
            ypred3i = [ypred2[j][i] for j in range(len(ypred2))]
            ypred3i = self._merge(ypred3i,mode)
            ypred3.append(ypred3i)

        return ypred3

    def _predict3(self,iclf,xte):
        clf,xtr = iclf
        simMatTe = self._makeKernel(xte,xtr)
        ypred2i = clf.predict(simMatTe) # remember: ypred2i is a vector
        return ypred2i

    def _fit2(self,xtr,ytr):
        ## tuning
        clf = svm.SVC(kernel='precomputed')

        ## train
        simMatTr = self._makeKernel(xtr,xtr)
        clf.fit(simMatTr,ytr)

        return (clf,xtr)

    def _merge(self,yList,mode):
        y = None
        if mode=='hard':
            y = Counter(yList).most_common(1)[0][0]
        else:
            assert False,'FATAL: unkown mode'
        return y

    def _divideSamples(self,x,y,maxSamples):
        # we abusely use StratifiedKFold, taking only the testIdx
        nSplits = int(len(x)/maxSamples) + 1
        if y is None:
            cv = KFold(n_splits=nSplits)
            idxesList = [testIdx for  _, testIdx in cv.split(x) ]
        else:
            cv = StratifiedKFold(n_splits=nSplits,shuffle=True)
            idxesList = [testIdx for  _, testIdx in cv.split(x,y) ]

        xyList = []
        for idxes in idxesList:
            xList = [x[i] for i in idxes]
            if y is None:
                xyList.append( (xList,None))
            else:
                yList = [y[i] for i in idxes]
                xyList.append( (xList,yList) )

        return xyList

    def _makeKernel(self,xtr1,xtr2):
        mat = np.zeros( (len(xtr1),len(xtr2)) )
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                mat[i][j] = self._getCompoundProteinSim(xtr1[i],xtr2[j])

        return mat

    def _getCompoundProteinSim(self,i,j):
        comSim = self._getCompoundSim(i[0],j[0])
        proSim = self._getProteinSim(i[1],j[1])

        alpha = 0.5
        sim = alpha*comSim + (1.0-alpha)*proSim

        return sim

    def _getCompoundSim(self,i,j):
        return self._simDict['com'][(i,j)]

    def _getProteinSim(self,i,j):
        return self._simDict['pro'][(i,j)]

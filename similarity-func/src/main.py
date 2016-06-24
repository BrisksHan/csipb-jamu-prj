# import library
import time
import operator
import numpy as np
import sys
from collections import OrderedDict
from collections import defaultdict
import os
import pickle
import shutil

# import our costum modules
import config as cfg
import util
import fitness_func as ff

# import deap
from deap import tools as deapTools
from deap import base as deapBase
from deap import creator as deapCreator
from deap import gp as deapGP

def main(argv):
##### Init 
    assert len(argv)==2

    # set D_tr
    datasetName = argv[1]
    data = util.loadData( cfg.datasetPaths[datasetName] )

    # init log
    tag = argv[1]
    dirpath = cfg.xprmtDir+"/"+"xprmt-"+tag+"."+time.strftime("%Y%m%d-%H%M%S")
    os.makedirs(dirpath)
    shutil.copy2('config.py', dirpath+'/config.py')

    statFit = deapTools.Statistics(lambda ind: ind.fitness.values)
    statSize = deapTools.Statistics(len)
    
    mstats = deapTools.MultiStatistics(fitness=statFit, size=statSize)
    mstats.register("min", np.min)
    mstats.register("max", np.max)
    mstats.register("avg", np.mean)
    mstats.register("std", np.std)
    
    logbook = deapTools.Logbook()
    logbook.header = ['gen'] + mstats.fields
    hofLog = []
    testKendalValidLog = []

##### init Deap GP
    # Set Operators and Operands 
    # Note: Tanimoto: (a/(a+b+c)), Forbes: ?
    nOperand = 4 # at most: a, b, c, d
    primitiveSet = deapGP.PrimitiveSet("mainPrimitiveSet", nOperand)
    primitiveSet.renameArguments(ARG0="a")
    primitiveSet.renameArguments(ARG1="b")
    primitiveSet.renameArguments(ARG2="c")
    primitiveSet.renameArguments(ARG3="d")

    primitiveSet.addPrimitive(np.add, arity=2, name="add")
    primitiveSet.addPrimitive(np.subtract, arity=2, name="sub")
    primitiveSet.addPrimitive(np.multiply, arity=2, name="mul")
    primitiveSet.addPrimitive(util.protectedDiv, arity=2, name="pDiv")

    # Adding new primitive set
    primitiveSet.addPrimitive(np.sqrt, arity=1, name="sqrt")
    primitiveSet.addPrimitive(util.pow, arity=1, name="pow")
    primitiveSet.addPrimitive(util.powhalf, arity=1, name="powhalf")
    primitiveSet.addPrimitive(np.log10, arity=1, name="log")
    primitiveSet.addPrimitive(np.minimum, arity=2, name="min")
    primitiveSet.addPrimitive(np.maximum, arity=2, name="max")
    primitiveSet.addEphemeralConstant("const", lambda: 0.5)

    # Settting up the fitness and the individuals
    deapCreator.create("FitnessMin", deapBase.Fitness, weights=(-1.0,)) # -1 because we minimize
    deapCreator.create("Individual", deapGP.PrimitiveTree, fitness=deapCreator.FitnessMin, primitiveSet=primitiveSet)

    # Setting up the operator of Genetic Programming such as Evaluation, Selection, Crossover, Mutation
    # register the generation functions into a Toolbox
    toolbox = deapBase.Toolbox()

    toolbox.register("expr", deapGP.genHalfAndHalf, # Half-full, halfGrow
                             pset=primitiveSet, 
                             min_=cfg.treeMinDepth, # tree min depth 
                             max_=cfg.treeMaxDepth) # tree min depth

    toolbox.register("individual", deapTools.initIterate, # alternatives: initRepeat, initCycle
                                   deapCreator.Individual,
                                   toolbox.expr)

    toolbox.register("population", deapTools.initRepeat,
                                   list,
                                   toolbox.individual)

    toolbox.register("compile", deapGP.compile, 
                                pset=primitiveSet)

    toolbox.register("select", deapTools.selRoulette)# : selRandom, selBest, selWorst, selTournament, selDoubleTournament
    toolbox.register("mate", deapGP.cxOnePoint)# :cxOnePointLeafBiased
    toolbox.register("expr_mut", deapGP.genFull, 
                                 min_=cfg.subtreeMinDepthMut, # subtree min depth
                                 max_=cfg.subtreeMaxDepthMut) # subtree min depth

    toolbox.register("mutate", deapGP.mutUniform, 
                                expr=toolbox.expr_mut,
                                pset=primitiveSet)

    toolbox.decorate("mate", deapGP.staticLimit(key=operator.attrgetter("height"), max_value=17))
    toolbox.decorate("mutate", deapGP.staticLimit(key=operator.attrgetter("height"), max_value=17))

    toolbox.register("exprTanimoto", util.tanimoto, pset=primitiveSet, min_=cfg.treeMinDepth, max_=cfg.treeMaxDepth)
    toolbox.register("indTanimoto", deapTools.initIterate, deapCreator.Individual, toolbox.exprTanimoto)
    toolbox.register("popTanimoto", deapTools.initRepeat, list, toolbox.indTanimoto)

    toolbox.register("exprForbes", util.forbes, pset=primitiveSet, min_=cfg.treeMinDepth, max_=cfg.treeMaxDepth)
    toolbox.register("indForbes", deapTools.initIterate, deapCreator.Individual, toolbox.exprForbes)
    toolbox.register("popForbes", deapTools.initRepeat, list, toolbox.indForbes)

### EVOLVE GENERATIONS
    pop = toolbox.population(cfg.nIndividual) # init pop   
    for g in range(cfg.nMaxGen):
        offspring = pop
        for i in offspring:
            print i
        assert False

        if (g > 0):
            # Select the next generation individuals
            offspring = toolbox.select(pop, len(pop))
            offspring = map(toolbox.clone, offspring)

            # Apply crossover on the offspring
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if np.random.binomial(1, cfg.pCx):
                    toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values

            # Apply mutation on the offspring
            for mutant in offspring:
                if np.random.binomial(1, cfg.pMut):
                    toolbox.mutate(mutant)
                    del mutant.fitness.values

        # Evaluate the entire population
        # print 'Evaluate the entire population ...'
        valid = False
        recallRankMat = None
        for i in range(cfg.maxKendallTrial):
            compiledPop = [toolbox.compile(expr=individual) for individual in offspring]
            valid,recallRankMat = ff.testKendal(compiledPop, data)
            if valid == True:
                break

        if valid:
            for idx,ind in enumerate(offspring):
                fitnessVal = np.mean( recallRankMat[idx,:] )
                ind.fitness.values = float(fitnessVal), # must be a tuple here
            testKendalValidLog.append('valid')
        else: # ignore this generation
            offspring = pop
            testKendalValidLog.append('invalid')
        
        # The population is entirely replaced by the offspring
        pop = offspring

        # Update log
        hof = deapTools.HallOfFame(cfg.nHOF)
        hof.update(pop)
        hofLog.append(hof)

        record = mstats.compile(pop) if mstats else {}
        logbook.record(gen=g, **record)
        print logbook.stream

        genDirpath = dirpath + "/gen-"+str(g)
        os.makedirs(genDirpath)

        np.savetxt(genDirpath + "/individual.csv", [f for f in pop], fmt='%s')
        np.savetxt(genDirpath + "/fitness.csv", [f.fitness.values for f in pop], fmt='%s')

        # Stopping criteria
        if ( util.isConverged(pop) ):
            break

### POST EVOLUTION
    genSummaryDirpath = dirpath + "/gen-summary"
    os.makedirs(genSummaryDirpath) 

    np.savetxt(genSummaryDirpath + "/individualHOF.csv", [[str(i) for i in j] for j in hofLog], fmt='%s', delimiter=',')
    np.savetxt(genSummaryDirpath + "/fitnessHOF.csv", [[i.fitness.values for i in j] for j in hofLog], fmt='%s', delimiter=',')
    np.savetxt(genSummaryDirpath + "/testKendalValidLog.csv", testKendalValidLog, fmt='%s', delimiter=',')

    evalPop = [] # compiled
    cTanimoto = toolbox.compile(expr=toolbox.popTanimoto(1)[0])
    evalPop.append( ('tanimoto',cTanimoto) )
    pickle.dump(cTanimoto, open(genSummaryDirpath+'/individual_tanimoto.pkl', "wb"),-1)
    cForbes = toolbox.compile(expr=toolbox.popForbes(1)[0])
    evalPop.append( ('forbes',cForbes) )
    pickle.dump(cForbes, open(genSummaryDirpath+'/individual_forbes.pkl', "wb"),-1)
    for idx,i in enumerate(hofLog[-1]):
        ci = toolbox.compile(expr=i)
        evalPop.append( ('gp'+str(idx),ci) )
        pickle.dump(ci, open(genSummaryDirpath+'/individual_gp'+str(idx)+'.pkl', "wb"),-1)
    
    valid = False
    recallRankMat = None
    for i in range(cfg.maxKendallTrial):
        valid,recallRankMat = ff.testKendal([i(1) for i in evalPop], data)
        if valid == True:
            break

    fitnessList = []
    if valid:
        for i in range(len(evalPop)):
            fitness = np.mean(recallRankMat[i,:])
            fitnessList.append(fitness)
    else:
        print 'WARN: testKendal in evalPop is invalid'

    # fitnessSortedIdx = ...

if __name__ == "__main__":
    start_time = time.time()
    main(sys.argv)
    print("GP done in: %s seconds" % (time.time() - start_time))

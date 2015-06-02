/** @file ActiveTagTextSerializer.cpp
 *
 * Contains the implementations of the serialization methods for ActiveTag.
 */
#include "ActiveTagTextSerializer.hpp"

#include <iostream>                     // for operator<<, basic_ostream, basic_ostream<>::__ostream_type, basic_istream<>::__istream_type

#include "global.hpp"                     // for make_unique
#include "problems/shared/GridPosition.hpp"  // for GridPosition
#include "solver/abstract-problem/Action.hpp"
#include "solver/abstract-problem/Observation.hpp"
#include "solver/abstract-problem/State.hpp"             // for State
#include "solver/serialization/TextSerializer.hpp"    // for TextSerializer

#include "solver/mappings/actions/enumerated_actions.hpp"
#include "solver/mappings/observations/discrete_observations.hpp"

#include "ActiveTagAction.hpp"
#include "ActiveTagModel.hpp"
#include "ActiveTagObservation.hpp"
#include "ActiveTagState.hpp"                 // for ActiveTagState

namespace solver {
class Solver;
} /* namespace solver */

namespace activetag {
void saveVector(std::vector<long> values, std::ostream &os) {
    os << "(";
    for (auto it = values.begin(); it != values.end(); it++) {
        os << *it;
        if ((it + 1) != values.end()) {
            os << ", ";
        }
    }
    os << ")";
}

std::vector<long> loadVector(std::istream &is) {
    std::vector<long> values;
    std::string tmpStr;
    std::getline(is, tmpStr, '(');
    std::getline(is, tmpStr, ')');
    std::istringstream sstr(tmpStr);
    while (std::getline(sstr, tmpStr, ',')) {
        long value;
        std::istringstream(tmpStr) >> value;
        values.push_back(value);
    }
    return values;
}

ActiveTagTextSerializer::ActiveTagTextSerializer(solver::Solver *solver) :
    solver::Serializer(solver) {
}

/* ------------------ Saving change sequences -------------------- */
void ActiveTagTextSerializer::saveModelChange(solver::ModelChange const &change, std::ostream &os) {
    ActiveTagChange const &activetagChange = static_cast<ActiveTagChange const &>(change);
    os << activetagChange.changeType;
    os << ": ";
    saveVector(std::vector<long> {activetagChange.i0, activetagChange.j0}, os);
    os << " ";
    saveVector(std::vector<long> {activetagChange.i1, activetagChange.j1}, os);
}
std::unique_ptr<solver::ModelChange> ActiveTagTextSerializer::loadModelChange(std::istream &is) {
    std::unique_ptr<ActiveTagChange> change = std::make_unique<ActiveTagChange>();
    std::getline(is, change->changeType, ':');
    std::vector<long> v0 = loadVector(is);
    std::vector<long> v1 = loadVector(is);
    change->i0 = v0[0];
    change->j0 = v0[1];
    change->i1 = v1[0];
    change->j1 = v1[1];
    return std::move(change);
}

void ActiveTagTextSerializer::saveState(solver::State const *state, std::ostream &os) {
    ActiveTagState const &activetagState = static_cast<ActiveTagState const &>(*state);
    os << activetagState.robotPos_.i << " " << activetagState.robotPos_.j << " "
       << activetagState.opponentPos_.i << " " << activetagState.opponentPos_.j << " "
       << (activetagState.isTagged_ ? "T" : "_");
}

std::unique_ptr<solver::State> ActiveTagTextSerializer::loadState(std::istream &is) {
    long i, j;
    is >> i >> j;
    GridPosition robotPos(i, j);
    is >> i >> j;
    GridPosition opponentPos(i, j);
    std::string activetaggedString;
    is >> activetaggedString;
    bool isTagged = (activetaggedString == "T");
    return std::make_unique<ActiveTagState>(robotPos, opponentPos, isTagged);
}


void ActiveTagTextSerializer::saveObservation(solver::Observation const *obs,
        std::ostream &os) {
    if (obs == nullptr) {
        os << "()";
    } else {
        // ActiveTagObservation const &observation = static_cast<ActiveTagObservation const &>(
        //         *obs);
        // os << "(" << observation.position_.i << " " << observation.position_.j;
        // os << " " << (observation.seesOpponent_ ? "SEEN" : "UNSEEN") << ")";
    }
}

std::unique_ptr<solver::Observation> ActiveTagTextSerializer::loadObservation(
        std::istream &is) {
    std::string obsString;
    std::getline(is, obsString, '(');
    std::getline(is, obsString, ')');
    if (obsString == "") {
        return nullptr;
    }
    long i, j;
    std::string tmpStr;
    std::istringstream(obsString) >> i >> j >> tmpStr;
    bool seesOpponent = tmpStr == "SEEN";
    return std::make_unique<ActiveTagObservation>(GridPosition(i, j), seesOpponent);
}


void ActiveTagTextSerializer::saveAction(solver::Action const *action,
        std::ostream &os) {
    if (action == nullptr) {
        os << "NULL";
        return;
    }
    ActiveTagAction const &a =
            static_cast<ActiveTagAction const &>(*action);
    ActionType code = a.getActionType();
    switch (code) {
    case ActionType::NORTH:
        os << "NORTH";
        break;
    case ActionType::EAST:
        os << "EAST";
        break;
    case ActionType::SOUTH:
        os << "SOUTH";
        break;
    case ActionType::WEST:
        os << "WEST";
        break;
    case ActionType::TAG:
        os << "TAG";
        break;
    default:
        os << "ERROR-" << static_cast<long>(code);
        break;
    }
}

std::unique_ptr<solver::Action> ActiveTagTextSerializer::loadAction(
        std::istream &is) {
    std::string text;
    is >> text;
    if (text == "NULL") {
        return nullptr;
    } else if (text == "NORTH") {
        return std::make_unique<ActiveTagAction>(ActionType::NORTH);
    } else if (text == "EAST") {
        return std::make_unique<ActiveTagAction>(ActionType::EAST);
    } else if (text == "SOUTH") {
        return std::make_unique<ActiveTagAction>(ActionType::SOUTH);
    } else if (text == "WEST") {
        return std::make_unique<ActiveTagAction>(ActionType::WEST);
    } else if (text == "TAG") {
        return std::make_unique<ActiveTagAction>(ActionType::TAG);
    } else {
        std::string tmpStr;
        std::istringstream sstr(text);
        std::getline(sstr, tmpStr, '-');
        long code;
        sstr >> code;
        debug::show_message("ERROR: Invalid action!");
        return std::make_unique<ActiveTagAction>(
                static_cast<ActionType>(code));
    }
}


int ActiveTagTextSerializer::getActionColumnWidth(){
    return 5;
}
int ActiveTagTextSerializer::getTPColumnWidth() {
    return 0;
}
int ActiveTagTextSerializer::getObservationColumnWidth() {
    return 12;
}
} /* namespace activetag */

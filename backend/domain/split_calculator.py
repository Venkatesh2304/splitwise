from typing import Dict, List, Tuple

class SplitType:
    EQUAL = 'EQUAL'
    EXACT = 'EXACT'
    PERCENTAGE = 'PERCENTAGE'
    SHARES = 'SHARES'

def calculate_splits(
    total_amount: float,
    split_type: str,
    participant_ids: List[int],
    custom_values: Dict[int, float] = None
) -> Tuple[Dict[int, float], str]:
    """
    Validates and calculates exact owed amounts per participant.
    
    :param total_amount: Total expense amount.
    :param split_type: EQUAL, EXACT, PERCENTAGE, or SHARES.
    :param participant_ids: List of user IDs participating in the expense.
    :param custom_values: Map of user_id -> exact amount (for EXACT), percentage (for
           PERCENTAGE), or number of shares (for SHARES).
    :return: Tuple of (owed_amounts_map: dict[user_id, float], error_message: str or None)
    """
    if total_amount <= 0:
        return {}, "Expense amount must be greater than zero."
    
    if not participant_ids:
        return {}, "At least one participant must be included in the split."

    custom_values = custom_values or {}
    owed_amounts = {}

    if split_type == SplitType.EQUAL:
        n = len(participant_ids)
        base_share = round(total_amount / n, 2)
        owed_amounts = {uid: base_share for uid in participant_ids}
        
        # Adjust rounding difference on the first participant so sum equals total_amount
        calculated_sum = sum(owed_amounts.values())
        diff = round(total_amount - calculated_sum, 2)
        if diff != 0 and participant_ids:
            owed_amounts[participant_ids[0]] = round(owed_amounts[participant_ids[0]] + diff, 2)
        
        return owed_amounts, None

    elif split_type == SplitType.EXACT:
        total_exact = round(sum(custom_values.get(uid, 0.0) for uid in participant_ids), 2)
        if abs(total_exact - round(total_amount, 2)) > 0.01:
            return {}, f"Exact shares sum to {total_exact:.2f}, but expense total is {total_amount:.2f}."
        
        for uid in participant_ids:
            owed_amounts[uid] = round(custom_values.get(uid, 0.0), 2)
        return owed_amounts, None

    elif split_type == SplitType.PERCENTAGE:
        total_pct = round(sum(custom_values.get(uid, 0.0) for uid in participant_ids), 2)
        if abs(total_pct - 100.0) > 0.01:
            return {}, f"Percentages sum to {total_pct:.2f}%, but must equal 100%."
        
        calculated_sum = 0.0
        for uid in participant_ids:
            pct = custom_values.get(uid, 0.0)
            share = round((total_amount * pct) / 100.0, 2)
            owed_amounts[uid] = share
            calculated_sum += share
            
        diff = round(total_amount - calculated_sum, 2)
        if diff != 0 and participant_ids:
            owed_amounts[participant_ids[0]] = round(owed_amounts[participant_ids[0]] + diff, 2)
            
        return owed_amounts, None

    elif split_type == SplitType.SHARES:
        # Two people in one room take 2 shares, someone on the sofa takes 1: the bill is
        # divided in proportion, so nobody has to work out the percentages themselves.
        units = {uid: custom_values.get(uid, 0.0) for uid in participant_ids}
        if any(u < 0 for u in units.values()):
            return {}, "A number of shares can't be less than zero."

        total_units = sum(units.values())
        if total_units <= 0:
            return {}, "Give at least one person a share of this expense."

        # Worked in whole paise: everyone is floored first, then the paise left over go
        # one at a time to whoever the flooring shortchanged most, so a share is never
        # out by more than 0.01 and the shares still add up to the total exactly.
        total_paise = int(round(total_amount * 100))
        exact = {uid: (total_paise * units[uid]) / total_units for uid in participant_ids}
        allotted = {uid: int(exact[uid]) for uid in participant_ids}
        order = {uid: position for position, uid in enumerate(participant_ids)}
        shortchanged = sorted(
            participant_ids,
            key=lambda uid: (-(exact[uid] - allotted[uid]), order[uid])
        )
        for uid in shortchanged[:total_paise - sum(allotted.values())]:
            allotted[uid] += 1

        return {uid: round(allotted[uid] / 100.0, 2) for uid in participant_ids}, None

    return {}, f"Invalid split type '{split_type}'."

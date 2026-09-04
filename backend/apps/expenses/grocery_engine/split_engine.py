import json
from typing import Dict, Any, List, Optional
from apps.groups.models import Group
from apps.users.models import UserProfile
from apps.expenses.models import Expense, ExpensePayer, ExpenseShare

class GrocerySplitEngine:
    """Universal Splitting Engine for any Grocery Platform (Blinkit, Swiggy Instamart, Zepto, etc.)."""

    @staticmethod
    def process_split(
        platform_name: str,
        group_id: Optional[int],
        buyer_id: Optional[int],
        order_id: str,
        total_amount: float,
        split_mode: str = "ITEMIZED",
        item_splits_data: Optional[List[Dict[str, Any]]] = None,
        bill_split_data: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        placed_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes itemized or bill-level splitting, calculates exact proportional fee distributions,
        and saves the expense to the database.
        """
        if not description or not str(description).strip():
            description = f"{platform_name.title()} Order #{order_id}"
        else:
            description = str(description).strip()

        # 1. Resolve Group
        group = Group.objects.filter(id=group_id).first() if group_id else None
        if not group:
            group = Group.objects.filter(name__icontains="groceries").first() or Group.objects.first()

        if not group:
            raise ValueError("No valid group found for splitting.")

        # 2. Resolve Buyer/Payer
        buyer = UserProfile.objects.filter(id=buyer_id).first() if buyer_id else None
        if not buyer:
            buyer = UserProfile.objects.filter(username="venkatesh").first() or group.members.first()

        if not buyer:
            raise ValueError("No valid buyer profile found.")

        all_members = list(group.members.all())
        member_ids = [m.id for m in all_members]
        owed_amounts = {m_id: 0.0 for m_id in member_ids}

        # Populate products_json_list for both BILL_LEVEL and ITEMIZED splits
        products_json_list = []
        if item_splits_data:
            for it in item_splits_data:
                assigned = it.get("assigned_member_ids", member_ids) if split_mode == "ITEMIZED" else member_ids
                assigned_names = [m.name.split(' ')[0] for m in all_members if m.id in assigned]
                products_json_list.append({
                    "name": it.get("name"),
                    "price": float(it.get("price", 0.0)),
                    "split_type": it.get("split_type", "ALL") if split_mode == "ITEMIZED" else "ALL",
                    "assigned_member_ids": assigned,
                    "assigned_names": assigned_names
                })

        # 3. Calculate Itemized vs Bill-Level Splits
        if split_mode == "BILL_LEVEL":
            b_type = bill_split_data.get("type", "ALL") if bill_split_data else "ALL"
            if b_type == "CUSTOM" and bill_split_data and "custom_amounts" in bill_split_data:
                custom_dict = bill_split_data.get("custom_amounts", {})
                for m_id in member_ids:
                    val = float(custom_dict.get(str(m_id), 0.0) or 0.0)
                    owed_amounts[m_id] = round(val, 2)
                
                diff = round(total_amount - sum(owed_amounts.values()), 2)
                if diff != 0 and buyer.id in owed_amounts:
                    owed_amounts[buyer.id] = round(owed_amounts[buyer.id] + diff, 2)
            else:
                assigned_ids = member_ids
                if bill_split_data and "member_ids" in bill_split_data:
                    assigned_ids = [m_id for m_id in bill_split_data["member_ids"] if m_id in member_ids]
                if not assigned_ids:
                    assigned_ids = member_ids

                n = len(assigned_ids)
                share_per_person = round(total_amount / n, 2)
                for m_id in assigned_ids:
                    owed_amounts[m_id] = share_per_person
                
                diff = round(total_amount - sum(owed_amounts.values()), 2)
                if diff != 0 and assigned_ids:
                    owed_amounts[assigned_ids[0]] = round(owed_amounts[assigned_ids[0]] + diff, 2)

        elif split_mode == "ITEMIZED":
            sum_products = sum(it["price"] for it in products_json_list)
            common_fees = max(0.0, round(total_amount - sum_products, 2))

            temp_product_subtotals = {m_id: 0.0 for m_id in member_ids}

            for item in products_json_list:
                item_price = item["price"]
                item_mode = item["split_type"]
                
                if item_mode == "PERSONAL":
                    target_ids = item.get("assigned_member_ids", [])
                    personal_id = target_ids[0] if target_ids else buyer.id
                    if personal_id in temp_product_subtotals:
                        temp_product_subtotals[personal_id] += item_price
                elif item_mode == "ALL":
                    n = len(member_ids)
                    share = item_price / n if n > 0 else 0.0
                    for m_id in member_ids:
                        temp_product_subtotals[m_id] += share
                elif item_mode == "SPECIFIC":
                    target_ids = [m_id for m_id in item.get("assigned_member_ids", member_ids) if m_id in member_ids]
                    if not target_ids:
                        target_ids = member_ids
                    n = len(target_ids)
                    share = item_price / n if n > 0 else 0.0
                    for m_id in target_ids:
                        if m_id in temp_product_subtotals:
                            temp_product_subtotals[m_id] += share

            total_subtotals_sum = sum(temp_product_subtotals.values()) or 1.0

            # Distribute common fees proportionally based on each person's item subtotal
            for m_id in member_ids:
                sub = temp_product_subtotals[m_id]
                fee_share = (sub / total_subtotals_sum) * common_fees if common_fees > 0 else 0.0
                owed_amounts[m_id] = round(sub + fee_share, 2)

            calc_total = sum(owed_amounts.values())
            diff = round(total_amount - calc_total, 2)
            if diff != 0 and buyer.id in owed_amounts:
                owed_amounts[buyer.id] = round(owed_amounts[buyer.id] + diff, 2)

        # 4. Save Expense to Database
        placed_at_str = str(placed_at or "").strip()
        notes_dict = {
            "platform": platform_name,
            "split_mode": split_mode,
            "placed_at": placed_at_str,
            "items": products_json_list
        }
        notes_str = json.dumps(notes_dict)

        # Delete any pre-existing split for this order ID
        Expense.objects.filter(description__icontains=str(order_id)).delete()

        expense = Expense.objects.create(
            group=group,
            description=description,
            amount=total_amount,
            category="FOOD",
            split_type="CUSTOM",
            created_by=buyer,
            notes=notes_str
        )

        ExpensePayer.objects.create(
            expense=expense,
            user=buyer,
            amount_paid=total_amount
        )

        for m_id, owed in owed_amounts.items():
            user_inst = UserProfile.objects.filter(id=m_id).first()
            if user_inst:
                ExpenseShare.objects.create(
                    expense=expense,
                    user=user_inst,
                    amount_owed=owed,
                    percentage=round((owed / total_amount) * 100, 2) if total_amount > 0 else 0.0
                )

        return {
            "message": f"Successfully split '{description}' into group '{group.name}'!",
            "expense_id": expense.id,
            "owed_breakdown": owed_amounts
        }

    @staticmethod
    def remove_split(order_id: str) -> Dict[str, Any]:
        """Deletes any expense corresponding to the given order ID."""
        deleted_count, _ = Expense.objects.filter(description__icontains=str(order_id)).delete()
        return {
            "ok": True,
            "message": f"Removed split for order #{order_id} ({deleted_count} expense deleted)."
        }

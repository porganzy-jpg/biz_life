"""
BarcodeQuest Guild System

Co-op guild system with guild creation, membership, ranking,
and co-op boss battles.
"""
import random
import time
import json
from datetime import datetime
from typing import Optional, List, Dict

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Text, ForeignKey
from sqlalchemy import desc, func
from sqlalchemy.orm import Session as DBSession

from database import Base, SessionLocal


# =====================================================
#  SQLAlchemy Models
# =====================================================

class Guild(Base):
    """
    Guild entity.
    Each guild has a name, leader, level, experience, and creation timestamp.
    """
    __tablename__ = "guilds"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    leader_id = Column(String(100), nullable=False)
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    description = Column(String(200), default="")
    max_members = Column(Integer, default=20)
    created_at = Column(DateTime, default=datetime.utcnow)


class GuildMember(Base):
    """
    Guild membership record.
    Each session can belong to at most one guild.
    role: 'leader', 'officer', 'member'
    """
    __tablename__ = "guild_members"

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    role = Column(String(20), default="member")
    contribution = Column(Integer, default=0)
    joined_at = Column(DateTime, default=datetime.utcnow)


class GuildBossLog(Base):
    """
    Log of guild boss battles.
    """
    __tablename__ = "guild_boss_logs"

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(Integer, nullable=False, index=True)
    boss_name = Column(String(100), nullable=False)
    boss_level = Column(Integer, default=1)
    total_damage = Column(Integer, default=0)
    result = Column(String(10), default="lose")  # win / lose
    participants_json = Column(JSON, default=list)
    rewards_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


# =====================================================
#  Constants
# =====================================================

GUILD_CREATE_COST = 5000  # gold
GUILD_LEVEL_EXP = [0, 100, 300, 600, 1000, 1500, 2200, 3000, 4000, 5500]  # exp needed per level
GUILD_MAX_LEVEL = 10

BOSS_NAMES = [
    ("Inferno Wyrm", "Fire", 500),
    ("Abyssal Kraken", "Water", 600),
    ("Ancient Treant", "Nature", 550),
    ("Mecha Overlord", "Tech", 650),
    ("Shadow Lich", "Dark", 700),
    ("Storm Titan", "Wind", 580),
    ("Crystal Golem", "Earth", 620),
    ("Void Devourer", "Spirit", 750),
]

BOSS_EMOJIS = {
    "Fire": "🔥", "Water": "🌊", "Nature": "🌳", "Tech": "🤖",
    "Dark": "💀", "Wind": "🌪️", "Earth": "🪨", "Spirit": "👻",
}


# =====================================================
#  GuildManager
# =====================================================

class GuildManager:
    """Guild system manager."""

    def _get_db(self) -> DBSession:
        return SessionLocal()

    # ----- Create Guild -----

    def create_guild(self, session_id: str, name: str, player_gold: int) -> dict:
        """
        Create a new guild.  Costs GUILD_CREATE_COST gold.

        Args:
            session_id: Creator's session ID
            name: Guild name (2-20 chars)
            player_gold: Creator's current gold (checked but NOT deducted here)

        Returns:
            dict with result or error
        """
        if not name or len(name.strip()) < 2 or len(name.strip()) > 20:
            return {"error": "길드 이름은 2~20자여야 합니다."}

        name = name.strip()

        if player_gold < GUILD_CREATE_COST:
            return {
                "error": f"골드가 부족합니다! (필요: {GUILD_CREATE_COST:,}G, 보유: {player_gold:,}G)"
            }

        db = self._get_db()
        try:
            # Check if already in a guild
            existing_member = db.query(GuildMember).filter(
                GuildMember.session_id == session_id
            ).first()
            if existing_member:
                return {"error": "이미 길드에 가입되어 있습니다. 먼저 탈퇴 후 생성해주세요."}

            # Check name uniqueness
            existing_guild = db.query(Guild).filter(Guild.name == name).first()
            if existing_guild:
                return {"error": f"'{name}' 이름의 길드가 이미 존재합니다."}

            # Create guild
            guild = Guild(
                name=name,
                leader_id=session_id,
                level=1,
                exp=0,
                created_at=datetime.utcnow(),
            )
            db.add(guild)
            db.flush()  # get guild.id

            # Add creator as leader
            member = GuildMember(
                guild_id=guild.id,
                session_id=session_id,
                role="leader",
                contribution=0,
                joined_at=datetime.utcnow(),
            )
            db.add(member)
            db.commit()

            return {
                "ok": True,
                "guild_id": guild.id,
                "guild_name": guild.name,
                "cost": GUILD_CREATE_COST,
                "message": f"'{name}' 길드가 생성되었습니다!",
            }
        finally:
            db.close()

    # ----- Join Guild -----

    def join_guild(self, session_id: str, guild_id: int) -> dict:
        """Join an existing guild."""
        db = self._get_db()
        try:
            # Check if already in a guild
            existing = db.query(GuildMember).filter(
                GuildMember.session_id == session_id
            ).first()
            if existing:
                return {"error": "이미 길드에 가입되어 있습니다."}

            guild = db.query(Guild).filter(Guild.id == guild_id).first()
            if not guild:
                return {"error": "길드를 찾을 수 없습니다."}

            # Check member count
            member_count = db.query(func.count(GuildMember.id)).filter(
                GuildMember.guild_id == guild_id
            ).scalar()
            if member_count >= guild.max_members:
                return {"error": "길드 인원이 가득 찼습니다."}

            member = GuildMember(
                guild_id=guild_id,
                session_id=session_id,
                role="member",
                contribution=0,
                joined_at=datetime.utcnow(),
            )
            db.add(member)
            db.commit()

            return {
                "ok": True,
                "guild_id": guild.id,
                "guild_name": guild.name,
                "message": f"'{guild.name}' 길드에 가입했습니다!",
            }
        finally:
            db.close()

    # ----- Leave Guild -----

    def leave_guild(self, session_id: str) -> dict:
        """Leave current guild.  Leaders cannot leave (must disband or transfer)."""
        db = self._get_db()
        try:
            member = db.query(GuildMember).filter(
                GuildMember.session_id == session_id
            ).first()
            if not member:
                return {"error": "길드에 가입되어 있지 않습니다."}

            guild = db.query(Guild).filter(Guild.id == member.guild_id).first()

            if member.role == "leader":
                # Check if there are other members
                other_count = db.query(func.count(GuildMember.id)).filter(
                    GuildMember.guild_id == member.guild_id,
                    GuildMember.session_id != session_id,
                ).scalar()
                if other_count > 0:
                    return {"error": "길드장은 다른 멤버가 있을 때 탈퇴할 수 없습니다. 길드장을 위임하거나 해산하세요."}
                # Last member = disband
                db.delete(member)
                if guild:
                    db.delete(guild)
                db.commit()
                return {"ok": True, "message": "길드가 해산되었습니다.", "disbanded": True}

            guild_name = guild.name if guild else "Unknown"
            db.delete(member)
            db.commit()
            return {"ok": True, "message": f"'{guild_name}' 길드에서 탈퇴했습니다."}
        finally:
            db.close()

    # ----- Get Guild Info -----

    def get_guild_info(self, session_id: str) -> dict:
        """Get the guild information for the player's current guild."""
        db = self._get_db()
        try:
            member = db.query(GuildMember).filter(
                GuildMember.session_id == session_id
            ).first()
            if not member:
                return {"in_guild": False, "message": "길드에 가입되어 있지 않습니다."}

            guild = db.query(Guild).filter(Guild.id == member.guild_id).first()
            if not guild:
                return {"in_guild": False, "message": "길드 정보를 찾을 수 없습니다."}

            # Get all members
            members = db.query(GuildMember).filter(
                GuildMember.guild_id == guild.id
            ).order_by(desc(GuildMember.contribution)).all()

            member_list = []
            for m in members:
                member_list.append({
                    "session_id": m.session_id,
                    "role": m.role,
                    "contribution": m.contribution,
                    "joined_at": m.joined_at.isoformat() if m.joined_at else "",
                })

            # Calculate level progress
            current_level = min(guild.level, GUILD_MAX_LEVEL)
            if current_level < GUILD_MAX_LEVEL:
                exp_needed = GUILD_LEVEL_EXP[current_level] if current_level < len(GUILD_LEVEL_EXP) else 9999
            else:
                exp_needed = 0

            return {
                "in_guild": True,
                "guild": {
                    "id": guild.id,
                    "name": guild.name,
                    "leader_id": guild.leader_id,
                    "level": guild.level,
                    "exp": guild.exp,
                    "exp_needed": exp_needed,
                    "description": guild.description,
                    "max_members": guild.max_members,
                    "member_count": len(member_list),
                    "created_at": guild.created_at.isoformat() if guild.created_at else "",
                },
                "members": member_list,
                "my_role": member.role,
                "my_contribution": member.contribution,
            }
        finally:
            db.close()

    # ----- Guild Ranking -----

    def guild_ranking(self, limit: int = 20) -> list:
        """Get top guilds by level and exp."""
        db = self._get_db()
        try:
            guilds = db.query(Guild).order_by(
                desc(Guild.level), desc(Guild.exp)
            ).limit(limit).all()

            ranking = []
            for i, g in enumerate(guilds):
                member_count = db.query(func.count(GuildMember.id)).filter(
                    GuildMember.guild_id == g.id
                ).scalar()
                ranking.append({
                    "rank": i + 1,
                    "guild_id": g.id,
                    "name": g.name,
                    "level": g.level,
                    "exp": g.exp,
                    "leader_id": g.leader_id,
                    "member_count": member_count,
                    "created_at": g.created_at.isoformat() if g.created_at else "",
                })
            return ranking
        finally:
            db.close()

    # ----- Guild Boss Battle -----

    def guild_boss_battle(self, session_id: str, party: list) -> dict:
        """
        Co-op guild boss battle.

        Combines the power of participating member's party to fight a guild boss.
        The boss scales with guild level.  Damage is calculated from party stats.

        Args:
            session_id: Session initiating the battle
            party: The initiator's party (list of monster dicts)

        Returns:
            dict with battle result, rewards, etc.
        """
        db = self._get_db()
        try:
            member = db.query(GuildMember).filter(
                GuildMember.session_id == session_id
            ).first()
            if not member:
                return {"error": "길드에 가입되어 있지 않습니다."}

            guild = db.query(Guild).filter(Guild.id == member.guild_id).first()
            if not guild:
                return {"error": "길드 정보를 찾을 수 없습니다."}

            if not party:
                return {"error": "파티에 몬스터가 없습니다!"}

            # Select boss based on guild level
            boss_idx = (guild.level - 1) % len(BOSS_NAMES)
            boss_name, boss_type, boss_base_hp = BOSS_NAMES[boss_idx]
            boss_level = guild.level * 5
            boss_hp = boss_base_hp + (guild.level * 100)
            boss_emoji = BOSS_EMOJIS.get(boss_type, "👹")

            # Calculate combined party power
            total_damage = 0
            battle_log = []

            for m in party[:3]:
                stats = m.get("stats", {})
                atk = stats.get("attack", 10)
                spd = stats.get("speed", 10)
                spc = stats.get("special", 10)
                m_level = m.get("level", 1)

                # Damage formula: (attack + special/2) * level_multiplier + random
                base_dmg = int((atk + spc * 0.5) * (1 + m_level * 0.05))
                crit = random.random() < 0.15
                if crit:
                    base_dmg = int(base_dmg * 1.5)

                total_damage += base_dmg
                battle_log.append({
                    "monster_name": m.get("name", "???"),
                    "damage": base_dmg,
                    "is_critical": crit,
                    "message": f"{m.get('name', '???')}이(가) {base_dmg} 데미지!" + (" (치명타!)" if crit else ""),
                })

            # Check if boss is defeated
            is_win = total_damage >= boss_hp

            # Rewards
            rewards = {
                "gold": 0,
                "exp": 0,
                "guild_exp": 0,
            }
            if is_win:
                rewards["gold"] = 200 + guild.level * 50
                rewards["exp"] = 50 + guild.level * 20
                rewards["guild_exp"] = 30 + guild.level * 10
            else:
                # Partial rewards based on damage dealt
                damage_ratio = min(1.0, total_damage / boss_hp)
                rewards["gold"] = int(50 * damage_ratio) + 20
                rewards["exp"] = int(20 * damage_ratio) + 10
                rewards["guild_exp"] = int(10 * damage_ratio) + 5

            # Update guild exp and level
            guild.exp += rewards["guild_exp"]

            # Check guild level up
            leveled_up = False
            while guild.level < GUILD_MAX_LEVEL:
                needed = GUILD_LEVEL_EXP[guild.level] if guild.level < len(GUILD_LEVEL_EXP) else 9999
                if guild.exp >= needed:
                    guild.exp -= needed
                    guild.level += 1
                    guild.max_members += 5
                    leveled_up = True
                else:
                    break

            # Update member contribution
            member.contribution += total_damage

            # Save boss log
            log_entry = GuildBossLog(
                guild_id=guild.id,
                boss_name=boss_name,
                boss_level=boss_level,
                total_damage=total_damage,
                result="win" if is_win else "lose",
                participants_json=[session_id],
                rewards_json=rewards,
                created_at=datetime.utcnow(),
            )
            db.add(log_entry)
            db.commit()

            return {
                "ok": True,
                "result": "WIN" if is_win else "LOSE",
                "boss": {
                    "name": boss_name,
                    "type": boss_type,
                    "emoji": boss_emoji,
                    "level": boss_level,
                    "hp": boss_hp,
                },
                "total_damage": total_damage,
                "damage_ratio": round(min(1.0, total_damage / boss_hp) * 100, 1),
                "battle_log": battle_log,
                "rewards": rewards,
                "guild_leveled_up": leveled_up,
                "guild_level": guild.level,
                "guild_exp": guild.exp,
                "my_contribution": member.contribution,
                "message": f"{boss_emoji} {boss_name}을(를) {'처치했습니다!' if is_win else '쓰러뜨리지 못했습니다...'}",
            }
        finally:
            db.close()

    # ----- Get Available Guilds (for browsing) -----

    def get_available_guilds(self, limit: int = 20) -> list:
        """Get a list of guilds that can be joined."""
        db = self._get_db()
        try:
            guilds = db.query(Guild).order_by(desc(Guild.level), desc(Guild.exp)).limit(limit).all()

            result = []
            for g in guilds:
                member_count = db.query(func.count(GuildMember.id)).filter(
                    GuildMember.guild_id == g.id
                ).scalar()
                if member_count < g.max_members:
                    result.append({
                        "guild_id": g.id,
                        "name": g.name,
                        "level": g.level,
                        "leader_id": g.leader_id,
                        "member_count": member_count,
                        "max_members": g.max_members,
                    })
            return result
        finally:
            db.close()

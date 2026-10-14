-- ka reshuffle times
select 
  case 
    when "day" = "day" then date_format(date(min_validated_at),'%Y/%m/%d')
    when "day" = "week" then subdate(date(min_validated_at),if(date_format(date(min_validated_at),'%w')=0,7,date_format(date(min_validated_at),'%w'))-1) 
    when "day" = "month" then date_format(date_add(date(min_validated_at), interval - day(date(min_validated_at)) + 1 day),'%Y/%m/01')
  end as period,
  cast(cnt as char) as ka_reshuffle_times,
	cid
from 
(
select *
from retail.ofp_ka_record m1 
join retail.ofp_user m2 on m1.cid=m2.id 
where cid='647592857382957385'
and date(validated_at)='2023-07-22'
and is_robot=0 
group by 1 
)a 
where min_validated_at > CURRENT_DATE - INTERVAL '7' day
group by 1,2 
order by 1 desc


-- ka_num in total & in every level and its percent
select count(DISTINCT m1.cid) as TTL_Valid_ka,
    count(distinct(if(level='BASIC',m1.cid,null))) 'BASIC',
    count(distinct(if(level='BASIC',m1.cid,null)))/count(DISTINCT m1.cid) 'B_rate',
    count(distinct(if(level='REGULAR',m1.cid,null)))'REGULAR',
    count(distinct(if(level='REGULAR',m1.cid,null)))/count(DISTINCT m1.cid) 'R_rate',
    count(distinct(if(level='PREMIUM',m1.cid,null))) 'PREMIUM',
    count(distinct(if(level='PREMIUM',m1.cid,null)))/count(DISTINCT m1.cid) 'P_rate'
from retail.ofp_ka_info m1 
join retail.ofp_user m2 on m2.id=m1.cid
where m2.is_robot=0 and m1.expired_at>now() and rna_area in ('CHINA','GLOBAL')


-- active ka and also active top20 as well as the superposition of active ka and active top20
select
	case
	when "week" = "day" then date_format(date(m2.created_at),'%Y/%m/%d')
	when "week" = "week" then subdate(date(m2.created_at),if(date_format(date(m2.created_at),'%w')=0,7,date_format(date(m2.created_at),'%w'))-1) 
	when "week" = "month" then date_format(date_add(date(m2.created_at), interval - day(date(m2.created_at)) + 1 day),'%Y/%m/01')
  end as period,
  count(distinct m1.cid) active_valid_ka,
	active_user_inselectedtime,
	count(distinct m1.cid)/active_user_inselectedtime as ka_pct_inactive,
	count(distinct(if(level='BASIC',m1.cid,null))) 'active_BASIC',
	count(distinct(if(level='BASIC',m1.cid,null)))/active_user_inselectedtime 'B_pct_inactive', -- how many pct of active users are ka of this level
	count(distinct(if(level='REGULAR',m1.cid,null)))'active_REGULAR',
	count(distinct(if(level='REGULAR',m1.cid,null)))/active_user_inselectedtime 'R_pct_inactive',
	count(distinct(if(level='PREMIUM',m1.cid,null))) 'active_PREMIUM',
	count(distinct(if(level='PREMIUM',m1.cid,null)))/active_user_inselectedtime 'P_pct_inactive'
from retail.ofp_ka_info m1
join retail.ofp_user_action_log m2 on m1.cid=m2.cid
join retail.ofp_user m3 on m3.id=m1.cid
join (
			select count(distinct m2.cid) active_user_inselectedtime 
      from retail.ofp_user_action_log m2,ofp_user m3 
      where m3.id=m2.cid and is_robot=0 and if(m3.rna_area='GLOBAL','CHINA',rna_area) = 'CHINA' and  m2.created_at BETWEEN FROM_UNIXTIME(1625097600) AND FROM_UNIXTIME(1625659132)
			) m4

where m3.is_robot=0
    and if(m3.rna_area='GLOBAL','CHINA',rna_area) = 'CHINA'
    and m1.expired_at>now()
    and m1.created_at<=m2.created_at
    and m2.created_at BETWEEN FROM_UNIXTIME(1625097600) AND FROM_UNIXTIME(1625659132)
group by 1
order by 1 desc

select count(distinct cid) from ofp_user_action_log m1
join retail.ofp_user m3 on m3.id=m1.cid
where m3.is_robot=0 and rna_area in ('CHINA','GLOBAL')

select * from retail.ofp_ka_info m1
join retail.ofp_user_action_log m2 on m1.cid=m2.cid
where m1.cid is null
limit 10


-- how many pct of active just registered (active here means existing any type of action)
select 
  date_format(m2.created_at,'%Y-%m-%d') register_dt,
  count(DISTINCT m2.cid) active,
  count(DISTINCT if(date(m2.created_at)=date(m1.created_at),m2.cid,null))/count(DISTINCT m2.cid) register_pct
from retail.ofp_user m1
join retail.ofp_user_action_log m2 on m1.id=m2.cid
where $__timeFilter(m2.created_at) and is_robot=0 and if(m1.rna_area='GLOBAL','CHINA',m1.rna_area) = $country
group by 1 


--ka distribution in balance and avtive_degree
select 
  case 
    when balances_tag='greener' then '2_Greener' 
    when balances_tag='bigFish' then '1_Big_Fish'
    when balances_tag='potential' then '3_Potential' 
    when balances_tag='newuser' then '4_New_user'
    when balances_tag='GLOBAL' then '5_GLOBAL' else '6_Error'
  end as balances_tag
  , count(distinct if(active_tag='active',m3.cid,null)) as active
  , count(distinct if(active_tag='normal',m3.cid,null)) as normal
  , count(distinct if(active_tag='pendingActivation',m3.cid,null)) as pendingActivation
  , count(distinct if(active_tag='suspicious',m3.cid,null)) as suspicious
  , count(distinct if(active_tag='churn',m3.cid,null)) as churn
  , count(distinct if(active_tag is null,m3.cid,null)) as "else"
  , count(distinct m3.cid) as TOTAL_ka_ofthebalancetag
from retail.ofp_user_tag m1 
join retail.ofp_ka_info m3 on m3.cid=m1.cid
join retail.ofp_user m2 on m2.id=m1.cid
where m2.is_robot=0 and if(m2.rna_area in ('CHINA','GLOBAL'),'CHINA','AMERICA') in ('CHINA')
group by 1
order by 1


-- the top20 usage: in saving_times and saving_amt
select cid,`level`,saving_amount,saving_count,validated_at,expired_at
from ofp_ka_info m1
join ofp_user m2 on m2.id=m1.cid
where m2.is_robot=0 and if(m2.rna_area in ('CHINA','GLOBAL'),'CHINA','AMERICA') in ('CHINA')
and expired_at>now()
group by 1
order by 3 desc,4 desc
limit 20


-- ka churn rate：from ka to non-ka/no longer active since when

-- new ka and churned user_cnt in a specified period to see if it's continuable


-- ka in organization and individual
select count(id) as group_cnt,rna_type from ofp_user 
where is_robot=0 and if(rna_area in ('CHINA','GLOBAL'),'CHINA','AMERICA') in ('CHINA')
group by 2

-- interval from register to ka (see how long a user needs growing to ka)


-- conversion funnel after register
select 
  period,convert_period,register,
  try_rna1/register as register_to_try_rna1,
  rna1_succ/try_rna1 as rna1_succ,
  try_deposit/rna1_succ as rna1_to_try_deposit,
  deposit_succ/try_deposit as deposit_succ,
  rna1_succ/register as reg_to_rna1_succ,
  deposit_succ/register as reg_to_deposit_succ,
  trade/deposit_succ as deposit_succ_to_trade,
  trade/register as reg_to_trade,
  trade_all_amt
from 
(
  select 
    case 
      when "[[by]]" = "day" then date(register_time)
      when "[[by]]" = "week" then subdate(date(register_time),if(date_format(date(register_time),'%w')=0,7,date_format(date(register_time),'%w'))-1) 
      when "[[by]]" = "month" then date_format(register_time,'%Y-%m-01')
    end as period
    , 'same_day_as_register' as convert_period
    , count(DISTINCT m1.cid) as register
    , count(DISTINCT if(date(min_rna1_submit_time)=date(register_time),m1.cid,null)) as try_rna1
    , count(DISTINCT if(date(min_rna1_succ_time)=date(register_time),m1.cid,null)) as rna1_succ 
    , count(DISTINCT if(date(min_try_deposit_time)=date(register_time),m1.cid,null)) as try_deposit
    , count(DISTINCT if(date(min_deposit_time)=date(register_time),m1.cid,null)) as deposit_succ
    , count(DISTINCT if(date(min_trade_time)=date(register_time),m1.cid,null)) as trade
    , count(DISTINCT if(date(min_trade_all_time)=date(register_time),m1.cid,null)) as trade_all 
    , sum(m2.transaction_volume) as trade_all_amt
  from retail_db.ba_user m1
  left join retail_db.ba_succ_transaction m2 on m2.cid=m1.cid and m2.is_otc != 'OTC' and 
		(case 
      when "[[by]]" = "day" then date(register_time)
      when "[[by]]" = "week" then subdate(date(register_time),if(date_format(date(register_time),'%w')=0,7,date_format(date(register_time),'%w'))-1) 
      when "[[by]]" = "month" then date_format(register_time,'%Y-%m-01') end)=
		(case 
      when "[[by]]" = "day" then date(order_end_time)
      when "[[by]]" = "week" then subdate(date(order_end_time),if(date_format(date(order_end_time),'%w')=0,7,date_format(date(order_end_time),'%w'))-1) 
      when "[[by]]" = "month" then date_format(order_end_time,'%Y-%m-01') end)
  where $__timeFilter(register_time) and concat(m1.rna_area,'_',rna_type) in ($rna_area_type)
  and market_source in ($market_source) and register_device_type in ($device_type) and if(m1.rna_area='GLOBAL','CHINA',m1.rna_area) in ($country)
  group by 1 with rollup
)a 
where convert_period in ($convert_period)
order by 1 desc 

-- individual and institution rate
select
rna_type,
count(distinct a.id) as cnt,
case 
	when rna_type='INDIVIDUAL' then count(distinct a.id)/ttl_ka_cnt
	when rna_type='INSTITUTION' then count(distinct a.id)/ttl_ka_cnt
end as pct
from ofp_ka_info a
left join retail.ofp_user b on a.cid=b.id
join (
	select count(distinct cid) as ttl_ka_cnt from ofp_ka_info where expired_at>now()
) c
where b.is_robot=0 
and rna_area in ('CHINA','GLOBAL') -- ,'CHINA','AMERICA') in ('CHINA')
and a.expired_at > now()
-- and rna_type='INDIVIDUAL'
group by 1


select distinct record_type,change_type from ofp_point_account_record ;

select * from ofp_point_account_record where id ='758337659302022';

select max(available),min(available),avg(available) from ofp_point_account;
SELECT available from ofp_point_account order by 1 desc limit 50;

$__timeFilter(created_at)

select count(a.cid),elt(interval (a.available,0,3000,10000,5000000,50000000), '[0,3000)','[3000,10000)','[10000,5000000)','[5000000,50000000)','[50000000,+)') as groupby 
from ofp_point_account a
join ofp_user b on b.id=a.cid
where b.is_robot=0
and date(a.created_at) >= '2023-07-01' -- $__timeFilter(created_at) -- 
-- and b.is_canceled = 0
and if(b.rna_area in ('CHINA','GLOBAL'),'CHINA','AMERICA') in ('CHINA') -- ($country) -- 
group by 2 order by 2;

select b.*,b.cnt/a.ttl_cnt pct
from (select count(*) ttl_cnt from ofp_point_account a )a join (
select 
elt(interval (a.available,0,3000,10000,5000000,50000000), '[0,3000)','[3000,10000)','[10000,5000000)','[5000000,50000000)','[50000000,+)') as groupby,
count(a.cid) cnt
from ofp_point_account a
join ofp_user b on b.id=a.cid
where date(a.created_at) >= '2023-07-01' -- $__timeFilter(a.created_at)
and b.is_robot=0
and if(b.rna_area in ('CHINA','GLOBAL'),'CHINA','AMERICA') in ('CHINA') -- ($country)
group by 1
order by 1
) b on 1=1;



select a.*,a.cnt/ttl_cnt as pct_of_all from
(
select
  a.`level`,
  case
  when b.available < '3000' and b.available >= '0' then 'a.[0,3k)'
  when b.available >= '3000' and b.available < '10000' then 'b.[3k,1w)'
  when b.available >= '10000' and b.available < '5000000' then 'c.[1w,500w)'
  when b.available >= '5000000' then 'd.[500w,∞)'
	else 'no_points'
  end as `range`,
  count(DISTINCT(a.cid)) cnt
FROM retail.ofp_ka_info a
JOIN retail.ofp_user c on c.id = a.cid
LEFT JOIN retail.ofp_point_account b ON a.cid = b.cid
WHERE c.is_robot=0 
AND c.rna_area in ('CHINA','GLOBAL') 
GROUP BY 1 desc,2 with rollup
) a
join (select count(distinct a.cid) as ttl_cnt from retail.ofp_ka_info a)b on 1=1;

select id,`name` from ofp_user a where `name` is null limit 20;


select count(a.cid),a.`level`
from retail.ofp_ka_info a 
left join ofp_point_account  b on a.cid=b.cid
where b.cid is null
group by 2;


SELECT count(distinct a.cid)/count(distinct b.id) pct 
from ofp_point_account a right join ofp_user b on a.cid=b.id
where b.is_robot=0
and b.is_canceled=0
and b.is_frozen=0
and if(b.rna_area in ('CHINA','GLOBAL'),'CHINA','AMERICA') in ('CHINA')


SELECT
  a.cid,b.name,
  a.available points,
	c.*
from ofp_point_account a
join ofp_user b on b.id=a.cid
left join (
select distinct account_id,
	count(c.id) action_times,
  sum(if(change_type='I',amount,0)) get_points,
  -- sum(if(change_type='O',amount,0)) cost_points,
  ifnull(sum(if(change_type='I',amount,null))-sum(if(change_type='O',amount,null)),0) as diff
	from ofp_point_account_record c
	group by 1)c on c.account_id=a.id
where b.is_robot=0
and b.is_canceled=0
and b.is_frozen=0
and if(b.rna_area in ('CHINA','GLOBAL'),'CHINA','AMERICA') in ('CHINA')
group by 1
order by 3 desc
limit 20


select record_type,change_type 'I/O',count(distinct account_id) user_cnt,count(distinct id) case_cnt,count(distinct id)/count(distinct account_id) avg_case,avg(amount) avg_change from ofp_point_account_record ar group by 1

select 
date(ar.created_at),
 record_type,change_type 'I/O',count(distinct account_id) user_cnt,count(distinct id) case_cnt,count(distinct id)/count(distinct account_id) avg_case,avg(amount) avg_change 
from ofp_point_account_record ar 
where date(created_at) > '2023-07-01'
group by 1,2
limit 100

select * from ofp_point_account_record ar order by created_at desc limit 100;

select * from ofp_point_account_record a where account_id=669344449821683712; join (select * from ofp_point_account where cid=669344296003964928)b where a.account_id=b.id
select * from ofp_user where id=669344296003964928;
select * from retail_db.ba_user where cid=669344296003964928;
select * from retail_db.ba_succ_transaction where cid=669344296003964928 order by order_start_time;



SELECT
  a.cid,b.name,
  a.available points,
	c.action_times,
	c.get_points,
	c.cost_points,
	c.diff
from ofp_point_account a
join ofp_user b on b.id=a.cid
left join (
select distinct account_id,
	count(c.id) action_times,
  sum(if(change_type='I',amount,0)) get_points,
  sum(if(change_type='O',amount,0)) cost_points,
  sum(if(change_type='I',amount,0))-sum(if(change_type='O',amount,0)) as diff
	from ofp_point_account_record c
	group by 1)c on c.account_id=a.id
where b.is_robot=0
and b.is_canceled=0
and b.is_frozen=0
and if(b.rna_area in ('CHINA','GLOBAL'),'CHINA','AMERICA') in ('CHINA')
group by 1
order by 3 desc
limit 20


select cast(cid as char) cid,`level`,saving_amount,saving_count,date_format(date(validated_at),'%Y-%m-%d') validated_at
from ofp_ka_info m1
join ofp_user m2 on m2.id=m1.cid
where m2.is_robot=0 and m2.rna_area in ('CHINA','GLOBAL')
and expired_at>now()
group by 1
order by 3 desc,4 desc
limit 20

select a.*,
a.case_cnt/ttl_case_cnt case_rate,
a.user_cnt/ttl_user_id user_rate
from
(select date(ar.created_at) period,count(distinct ar.id) ttl_case_cnt,count(distinct ar.account_id) ttl_user_id from ofp_point_account_record ar group by 1) b
join (
select 
-- case 
-- 	when "day" = "day" then date(ar.created_at)
-- 	when "[[by]]" = "week" then subdate(date(ar.created_at),if(date_format(date(ar.created_at),'%w')=0,7,date_format(date(ar.created_at),'%w'))-1) 
-- 	when "[[by]]" = "month" then date_format(ar.created_at,'%Y-%m-01')
--   end 
	date(ar.created_at) as period,
  record_type,
	change_type 'I/O',count(distinct account_id) user_cnt,
  count(distinct id) case_cnt,
  count(distinct id)/count(distinct account_id) avg_case,
  avg(amount) avg_change
from ofp_point_account_record ar 
where ar.created_at > '2023-07-01'
group by 1 desc,2 with rollup
-- order by 1 desc
limit 100
) a on a.period=b.period



SELECT
  cast(a.cid as char) cid,
  b.name,
  a.available points,
	c.action_times,
	c.get_points,
	@i:=@i+1 rnk
from ofp_point_account as a
join ofp_user b on b.id=a.cid
left join (
	select distinct account_id,
	count(c.id) action_times,
  sum(if(change_type='I',amount,0)) get_points,
  sum(if(change_type='O',amount,0)) cost_points,
  max(created_at) created_at
	from ofp_point_account_record c
	group by 1
	having max(created_at)>'2023-07-01'
	order by 3 desc
	limit 50
)c on c.account_id=a.id
join (select @i:=0) it on 1=1
where b.is_robot=0
and b.is_canceled=0
and b.is_frozen=0
and if(b.rna_area in ('CHINA','GLOBAL'),'CHINA','AMERICA') in ('CHINA')
and c.created_at > '2023-07-01'
group by 1
order by get_points desc
limit 20




EXPLAIN SELECT
  cast(a.cid as char) cid,
  b.name,
  a.available points,
	c.action_times,
	c.get_points,
	@i:=@i+1 rnk
from ofp_point_account as a
join ofp_user b on b.id=a.cid
left join (
	select distinct account_id,
	count(c.id) action_times,
  sum(if(change_type='I',amount,0)) get_points,
  max(created_at) created_at
	from ofp_point_account_record c
	group by 1
	having max(created_at BETWEEN FROM_UNIXTIME(1627776000) AND FROM_UNIXTIME(1630454399))
	order by 3 desc
	limit 50
)c on c.account_id=a.id
join (select @i:=0) it on 1=1
where b.is_robot=0
and b.is_canceled=0
and b.is_frozen=0
and if(b.rna_area in ('CHINA','GLOBAL'),'CHINA','AMERICA') in ('CHINA')
and c.created_at BETWEEN FROM_UNIXTIME(1627776000) AND FROM_UNIXTIME(1630454399)
group by 1
order by get_points desc
limit 20



EXPLAIN select distinct account_id,
	count(c.id) action_times,
  sum(if(change_type='I',amount,0)) get_points,
  max(created_at) created_at
	from ofp_point_account_record c
	group by 1
	having max(created_at BETWEEN FROM_UNIXTIME(1627776000) AND FROM_UNIXTIME(1630454399))
	order by 3 desc
	limit 50


-- 20220114 修改ka活跃部分
select active_action from ba_user_active_snap a group by 1;
where active_group like 'ka%'

select calc_date as time,active_group,sum(active_cnt) as cid
from retail_db.ba_user_active_snap
where rna_area in ($country) and active_type='DAU' and active_action=1 and $__timeFilter(calc_date) and active_group in ('ka_adr','ka_web','ka_h5','ka_ios','ka_Google_app','ka_natural','ka_invited')
group by 1,2
order by 1,2;

select active_cnt
from retail_db.ba_user_active_snap
where calc_date=current_date - interval '1' day and rna_area in ($country) and active_type='DAU' and active_group='ka' and active_action=1


    -- 这种写法联表还是会重复计算，导致倍乘
select calc_date,
       sum(if(active_group='ka',active_cnt,null)) active_ka,
       sum(if(active_group='ka',active_cnt,null))/sum(if(active_group='ALL',active_cnt,null))active_ka_indau,
       -- sum(m2.cnt) over() as ka,

       sum(if(active_group='ka_1',active_cnt,null)) active_1,
       sum(if(active_group='ka_1',active_cnt,null))/sum(if(active_group='ka',active_cnt,null)) 1_pct_inactive,
       sum(if(active_group='ka_1',active_cnt,null))/sum(if(m2.effect_level=1,cnt,null)) active_pct_in1,

       sum(if(active_group='ka_2',active_cnt,null)) active_2,
       sum(if(active_group='ka_2',active_cnt,null))/sum(if(active_group='ka',active_cnt,null)) 2_pct_inactive,
       sum(if(active_group='ka_2',active_cnt,null))/sum(if(m2.effect_level=2,cnt,null)) active_pct_in2,

       sum(if(active_group='ka_3',active_cnt,null)) active_3,
       sum(if(active_group='ka_3',active_cnt,null))/sum(if(active_group='ka',active_cnt,null)) 3_pct_inactive,
       sum(if(active_group='ka_3',active_cnt,null))/sum(if(m2.effect_level=3,cnt,null)) active_pct_in3,

       sum(if(active_group='ka_4',active_cnt,null)) active_4,
       sum(if(active_group='ka_4',active_cnt,null))/sum(if(active_group='ka',active_cnt,null)) 4_pct_inactive,
       sum(if(active_group='ka_4',active_cnt,null))/sum(if(m2.effect_level=4,cnt,null)) active_pct_in4,

       sum(if(active_group='ka_5',active_cnt,null)) active_5,
       sum(if(active_group='ka_5',active_cnt,null))/sum(if(active_group='ka',active_cnt,null)) 5_pct_inactive,
       sum(if(active_group='ka_5',active_cnt,null))/sum(if(m2.effect_level=5,cnt,null)) active_pct_in5
from retail_db.ba_user_active_snap m1
left join (
    select effect_level,count(distinct cid) cnt
    from retail.ofp_ka_info a
    join retail.ofp_user b on a.cid=b.id and is_robot=0 and b.rna_area='CHINA'
    where effect_level>0
    group by 1 order by 1
    )m2 on 1=1
where m1.active_type='DAU' and m1.active_group in ('ka_1','ka_2','ka_3','ka_4','ka_5','ALL','ka') and m1.calc_date >=current_date-interval 7 day and m1.rna_area='CHINA'
group by 1 order by 1;

select calc_date,active_group,a.active_cnt/b.cnt as active_in_ka
from (select calc_date,substring_index(active_group,'_',-1) as active_group,active_cnt
from retail_db.ba_user_active_snap m1
where m1.active_type='DAU' and m1.active_group in ('ka_1','ka_2','ka_3','ka_4','ka_5')
  and m1.calc_date>=current_date-interval 7 day and m1.rna_area='CHINA' and active_action=1
  group by 1,2 order by 1)a
left join (
    select effect_level,count(distinct cid) cnt
    from retail.ofp_ka_info a
    join retail.ofp_user b on a.cid=b.id and is_robot=0 and b.rna_area='CHINA'
    where effect_level>0
    group by 1 order by 1
    )b on a.active_group=effect_level group by 1,2 order by 1,2;


select substring_index('ka_1','_',-1);

select cid from retail.ofp_user a join retail_db.ba_succ_transaction m2 on a.id=m2.cid where a.is_robot=1 group by 1; -- ba_succ_transaction表中没有测试用户

select effect_level,count(distinct cid) cnt
from retail.ofp_ka_info a
join retail.ofp_user b on a.cid=b.id and is_robot=0

select
       bb.active_user_inselectedtime,
       aa.active_valid_ka/bb.active_user_inselectedtime as 'ka_pct_inactive',
       aa.*
from
(
    select
        case
        when "[[by]]" = "day" then date_format(date(m2.created_at),'%Y/%m/%d')
        when "[[by]]" = "week" then subdate(date(m2.created_at),if(date_format(date(m2.created_at),'%w')=0,7,date_format(date(m2.created_at),'%w'))-1)
        when "[[by]]" = "month" then date_format(date_add(date(m2.created_at), interval - day(date(m2.created_at)) + 1 day),'%Y/%m/01')
        end as period,

        count(distinct m1.cid) 'active_valid_ka',
#         active_user_inselectedtime,
#         count(distinct m1.cid)/active_user_inselectedtime as 'ka_pct_inactive',
        current_valid_ka,
        count(distinct m1.cid)/current_valid_ka as 'active_pct_inka',

        count(distinct(if(effect_level=1,m1.cid,null))) 'active_1',
        count(distinct(if(effect_level=1,m1.cid,null)))/count(DISTINCT m1.cid) '1_pct_inactive', -- 活跃ka中有多少是这个level的
        count(distinct(if(effect_level=1,m1.cid,null)))/current_valid_ka 'active_pct_in1', -- -- 在该级别的有效ka总数中，有多少是活跃用户（既是该等级又是活跃的）

        count(distinct(if(effect_level=2,m1.cid,null)))'active_2',
        count(distinct(if(effect_level=2,m1.cid,null)))/count(DISTINCT m1.cid) '2_pct_inactive',
        count(distinct(if(effect_level=2,m1.cid,null)))/current_valid_ka 'active_pct_in2',

        count(distinct(if(effect_level=3,m1.cid,null))) 'active_3',
        count(distinct(if(effect_level=3,m1.cid,null)))/count(DISTINCT m1.cid) '3_pct_inactive',
        count(distinct(if(effect_level=3,m1.cid,null)))/current_valid_ka 'active_pct_in3',

        count(distinct(if(effect_level=4,m1.cid,null))) 'active_4',
        count(distinct(if(effect_level=4,m1.cid,null)))/count(DISTINCT m1.cid) '4_pct_inactive',
        count(distinct(if(effect_level=4,m1.cid,null)))/current_valid_ka 'active_pct_in4',

        count(distinct(if(effect_level=5,m1.cid,null))) 'active_5',
        count(distinct(if(effect_level=5,m1.cid,null)))/count(DISTINCT m1.cid) '5_pct_inactive',
        count(distinct(if(effect_level=5,m1.cid,null)))/current_valid_ka 'active_pct_in5'
    from retail.ofp_ka_info m1
    join retail.ofp_user_action_log m2 on m1.cid=m2.cid
    join retail.ofp_user m3 on m3.id=m1.cid
    left join (
        select count(DISTINCT m1.cid) as 'current_valid_ka'
        from retail.ofp_ka_info m1
        join retail.ofp_user m2 on m2.id=m1.cid
        where m2.is_robot=0 and m1.effect_level>0 and if(rna_area='GLOBAL','CHINA',rna_area) = $country
        )m4 on 1=1
    where m3.is_robot=0
    and if(m3.rna_area='GLOBAL','CHINA',rna_area) = $country
    and m1.effect_level>0
      and m1.created_at<=m2.created_at
    and $__timeFilter(m2.created_at)
    group by 1
    order by 1 desc
) aa left join (
	select
	case
	when "[[by]]" = "day" then date_format(date(m2.created_at),'%Y/%m/%d')
	when "[[by]]" = "week" then subdate(date(m2.created_at),if(date_format(date(m2.created_at),'%w')=0,7,date_format(date(m2.created_at),'%w'))-1)
	when "[[by]]" = "month" then date_format(date_add(date(m2.created_at), interval - day(date(m2.created_at)) + 1 day),'%Y/%m/01')
	end as period,
	count(distinct m2.cid) 'active_user_inselectedtime' from retail.ofp_user_action_log m2 where $__timeFilter(m2.created_at) group by 1 order by 1 desc
)bb on aa.period=bb.period;


select a.*,cid/sum(cid)over() as ttl from (
select calc_date as time,active_group,sum(active_cnt) as cid
from retail_db.ba_user_active_snap
where  active_type='DAU' and active_action=1 and calc_date=current_date and active_group in ('ka_Google_app','ka_natural','ka_invited') -- rna_area in ($country) and
group by 1,2 order by 1,2 )a


select a.*,cid/sum(cid)over(partition by time) as pct from (
select calc_date as time,active_group,sum(active_cnt) as cid
from retail_db.ba_user_active_snap
where rna_area in ('CHINA') and active_type='DAU' and active_action=1 and calc_date BETWEEN FROM_UNIXTIME(1641772800) AND FROM_UNIXTIME(1642377599) and active_group in ('ka_Google_app','ka_natural','ka_invited')
group by 1,2 order by 1,2 )a group by 1,2 order by 1,2



    -- todo transsaction_volume with timeseries
select
	case
    when "[[by]]" = "day" then date(order_end_time)
    when "[[by]]" = "week" then subdate(date(order_end_time),if(date_format(date(order_end_time),'%w')=0,7,date_format(date(order_end_time),'%w'))-1)
    when "[[by]]" = "month" then date_format(order_end_time,'%Y-%m-01')
  end as period,
	substring_index(ka_level,':',-1) ka_level,
	count(distinct m1.cid) as trader,
	count(distinct order_id) as case_cnt,
	sum(transaction_volume) as tx_amt,
	sum(commission_fee) as fee,
	sum(commission_fee)/sum(transaction_volume) as fee_rate,
	sum(if(order_type='agent_TX',transaction_volume,0)) as tx_amt_agent,
	sum(if(order_type='agent_TX',commission_fee,0))/sum(if(order_type='agent_TX',transaction_volume,0)) as fee_rate_agent,
	sum(if(order_type='distribution_TX',transaction_volume,0)) as tx_amt_distribution,
	sum(if(order_type='distribution_TX',commission_fee,0))/sum(if(order_type='distribution_TX',transaction_volume,0)) as fee_rate_distribution,
	sum(if(order_type='coupon_TX',transaction_volume,0)) as tx_amt_coupon,
	sum(if(order_type='coupon_TX',commission_fee,0))/sum(if(order_type='coupon_TX',transaction_volume,0)) as fee_rate_coupon
from retail_db.ba_succ_transaction m1,retail_db.ba_user m2
where m1.cid=m2.cid and $__timeFilter(order_end_time) and is_otc !='OTC' and record_type in ('SELL','BUY')
and if(m2.rna_area in ('CHINA','GLOBAL'),'CHINA','AMERICA') in ($country) and  ka_level not in ('ka:BASIC','SPECIAL','ka:NONE','NONE')
group by 1,2;

select a.*,trade_val/sum(trade_val) over(partition by period) as pct from (
select 	case
    when "[[by]]" = "day" then date(order_end_time)
    when "[[by]]" = "week" then subdate(date(order_end_time),if(date_format(date(order_end_time),'%w')=0,7,date_format(date(order_end_time),'%w'))-1)
    when "[[by]]" = "month" then date_format(order_end_time,'%Y-%m-01')
    end as period,
    effect_level,
    sum(transaction_volume) trade_val
from retail_db.ba_succ_transaction m1
join retail.ofp_ka_info m2 on m1.cid=m2.cid and effect_level>0
where m1.record_type in ('SELL','BUY') and $__timeFilter(order_end_time) and is_otc !='OTC' and if(m1.rna_area in ('CHINA','GLOBAL'),'CHINA','AMERICA') in ($country)
group by 1,2 order by 1,2)a;

select ka_level from retail_db.ba_succ_transaction m1 group by 1;

select str_to_date()

select a.*,trade_val/sum(trade_val) over(partition by time) as pct from (
select case
    when "day" = "day" then date(order_end_time)
    when "day" = "week" then subdate(date(order_end_time),if(date_format(date(order_end_time),'%w')=0,7,date_format(date(order_end_time),'%w'))-1)
    when "day" = "month" then str_to_date(date_format(order_end_time,'%Y-%m-01'),'%Y-%m-%d')
    end as time,
    effect_level,
    sum(transaction_volume) trade_val
from retail_db.ba_succ_transaction m1
join retail.ofp_ka_info m2 on m1.cid=m2.cid and effect_level>0
where m1.record_type in ('SELL','BUY') and order_end_time BETWEEN FROM_UNIXTIME(1641772800) AND FROM_UNIXTIME(1642377599)
  and is_otc !='OTC' and if(m1.rna_area in ('CHINA','GLOBAL'),'CHINA','AMERICA') in ('CHINA')
group by 1,2 order by 1,2)a group by 1,2 order by 1,2;











-- ---------------------------------------------------------------------------------------------------- --

-- 早期的思考，打算存历史等级表的
/*create table retali_db.ba_ka_snap like retail.ofp_ka_info;

alter table retali_db.ba_ka_snap add calc_date DATE(10) default not null comment '统计日期' after id;

insert ignore into retali_db.ba_ka_snap(id, cid, saving_amount, saving_count, created_at, updated_at,
                                                 area, auc, auc_updated_at, auc_level, redeem_level, redeem_validated_at,
                                                 redeem_expired_at, effect_type, effect_level)
select (id, cid, saving_amount, saving_count, created_at, updated_at,
                                                 area, auc, auc_updated_at, auc_level, redeem_level, redeem_validated_at,
                                                 redeem_expired_at, effect_type, effect_level)
from retail.ofp_ka_info a join retail.ofp_user b on a.cid=b.id where date(updated_at)=curdate() and b.is_robot=0;

update retali_db.ba_ka_snap a join (select date(current_date) cur)b on 1=1 set a.calc_date=cur;



/*update retali_db.ba_ka_snap join (
    select
    ) on
set
where*/

# select cid from retali_db.ba_succ_transaction a join ofp_user b on a.cid=b.id and is_robot=1;
# select date_format(curdate()-interval '2' day,'%Y-%m-%d %k-%i-%s');
# select count(1) from retail.ofp_ka_info a where date(updated_at)='2023-12-01';
# select * from ofp_ka_info a join ofp_user b on a.cid=b.id where is_robot=1; -- ka info表目前有459个测试用户*/
# select * from ofp_user where created_at>current_date


-- snap of active ka
-- 1.DAU；
insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt) -- DAU-all-login
select date(m1.created_at)                              as calc_date,
       if(m2.rna_area = 'GLOBAL', 'CHINA', m2.rna_area) as rna_area,
       'DAU'                                            as active_type,
       'ALL'                                            as active_group,
       1                                                as active_action,
       count(distinct m1.cid)                      cnt
from retail.ofp_user_action_log m1
         join retali_db.ba_user m2 on m2.cid = m1.cid
where m1.created_at >= current_date - interval '2' day
group by 1, 2, 3, 4, 5
order by 1, 2, 3, 4, 5
on duplicate key update active_cnt = cnt -- 实现了如果前面的字段已经全部存在的话，就只是更新active_cnt。如果没有相同行，就插入一条新的记录。
;

-- 2.MAU（in diiferent levels/market_source/terminal_device市场渠道、终端设备三种类型）
insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt) -- MAU-all-login
select m2.start_dt                                      as calc_date,
       if(m0.rna_area = 'GLOBAL', 'CHINA', m0.rna_area) as rna_area,
       'MAU'                                            as active_type,
       'ALL'                                            as active_group,
       1                                                as active_action,
       count(DISTINCT m1.cid)                           as cnt
from retali_db.ba_user m0
join retail.ofp_user_action_log m1 on m0.cid = m1.cid
join (
    select a.register_time as start_dt, date(b.register_time) end_dt
    from (
          select distinct date(register_time) register_time
          from retali_db.ba_user
          where register_time >= current_date - interval '2' day
      ) a
    join retali_db.ba_user b on a.register_time >= date(b.register_time) and a.register_time < date(b.register_time) + interval '30' day
    group by 1, 2
    order by 1, 2
) m2 on m2.end_dt = date(m1.created_at)
group by 1, 2, 3, 4, 5
order by 1, 2, 3, 4, 5
on duplicate key update active_cnt = cnt
;


-- other MAU timecost:14s
select calc_date,
       if(m0.rna_area = 'GLOBAL', 'CHINA', m0.rna_area) as rna_area,
       'MAU'                                            as active_type,
       'ALL'                                            as active_group,
       1                                                as active_action,
       count(DISTINCT m1.cid)                   as cnt
from (select cid,rna_area from retali_db.ba_user m0)m0
join (
    select calc_date,date(calc_date-interval 29 day) as start_dt
    from (
        select distinct date(register_time) calc_date
        from retali_db.ba_user
        where register_time >= current_date - interval '2' day
        ) a
    group by 1,2
    )m2 on 1=1
join (select cid,created_at from retail.ofp_user_action_log m1 where created_at>=current_date-interval 32 day)m1 on m0.cid = m1.cid and date(m1.created_at)>=m2.start_dt
group by 1,2,3,4,5 order by 1,2,3,4,5;

insert into retali_db.ba_user_active_snap(calc_date,rna_area,active_type,active_group,active_action,active_cnt)
-- DAU-device-login
select
date(m1.created_at) calc_date,
if(m2.rna_area='GLOBAL','CHINA',m2.rna_area) as rna_area,
'DAU' as active_type,
ifnull(m1.source_mark,'web') as active_group,
1 as active_action,
count(distinct m1.cid) cnt
from retail.ofp_user_action_log m1
join retali_db.ba_user m2 on m2.cid=m1.cid
where m1.created_at>=current_date - interval '2' day
group by 1,2,3,4,5
order by 1,2,3,4,5
on duplicate key update active_cnt = cnt
;


insert into retali_db.ba_user_active_snap(calc_date,rna_area,active_type,active_group,active_action,active_cnt)
-- DAU-market source-login
select
date(m1.created_at) calc_date,
if(m2.rna_area='GLOBAL','CHINA',m2.rna_area) as rna_area,
'DAU' as active_type,
m2.market_source as active_group,
1 as active_action,
count(distinct m1.cid) cnt
from retail.ofp_user_action_log m1
join retali_db.ba_user m2 on m2.cid=m1.cid
where m1.created_at>=current_date - interval '2' day and m2.market_source in ('Google_app','invited','natural')
group by 1,2,3,4,5
order by 1,2,3,4,5
on duplicate key update active_cnt = cnt
;

insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt)
-- DAU-all-trade_all
select order_end_dt                               as calc_date,
       if(rna_area = 'GLOBAL', 'CHINA', rna_area) as rna_area,
       'DAU'                                      as active_type,
       'ALL'                                      as active_group,
       2                                          as active_action,
       count(distinct cid)                           cnt
from retali_db.ba_succ_transaction
where order_end_dt >= current_date - interval '2' day
group by 1, 2, 3, 4, 5
order by 1, 2, 3, 4, 5
on duplicate key update active_cnt = cnt
;
--  days diff
insert into retali_db.ba_user_active_snap(calc_date,rna_area,active_type,active_group,active_action,active_cnt)
-- DAU days diff -all-login
select
a.calc_date,
a.rna_area,
case
  when diff_day<=7 then concat('DAU_DAYS_DIFF_',diff_day)
  when diff_day<=15 then 'DAU_DAYS_DIFF_a.[8,15]'
  when diff_day<=30 then 'DAU_DAYS_DIFF_b.[16,30]'
  when diff_day<=60 then 'DAU_DAYS_DIFF_c.[31,60]' else 'DAU_DAYS_DIFF_d.[61,max]' end as active_type,
'ALL' as active_group,
1 as active_action,
count(DISTINCT cid) as cnt
from
(
select
if(m1.rna_area='GLOBAL','CHINA',m1.rna_area) as rna_area,
m2.cid,
date(m2.created_at) as calc_date,
ifnull(timestampdiff(day,date(max(m3.created_at)),date(m2.created_at)),0) as diff_day
from retali_db.ba_user m1
join retail.ofp_user_action_log m2 on m1.cid=m2.cid
left join retail.ofp_user_action_log m3 on m2.cid =m3.cid and date(m3.created_at)<date(m2.created_at)
where date(m2.created_at)>=current_date - interval '2' day
group by 1,2,3
)a
group by 1,2,3,4,5
order by 1,2,3,4,5
on duplicate key update active_cnt = cnt
;

-- DAU ka
insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt)
-- DAU ka login
select date(m2.created_at) as calc_date,
       if(m3.rna_area = 'GLOBAL', 'CHINA', m3.rna_area) as rna_area,
       'DAU' as active_type,
       'ka' as active_group,
       1 as active_action,
       count(distinct m1.cid) as cnt
from retail.ofp_ka_info m1
    join retail.ofp_user_action_log m2 on m1.cid=m2.cid
    join retali_db.ba_user m3 on m3.cid=m1.cid
where m1.effect_level>0 and m2.created_at>=current_date
group by 1,2,3,4,5 order by 1,2,3,4,5
on duplicate key update active_cnt = cnt;

-- DAU ka in different levels (save in tinyint as varchar)
insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt)
-- DAU ka_level login
select date(m2.created_at) as calc_date,
       if(m3.rna_area = 'GLOBAL', 'CHINA', m3.rna_area) as rna_area,
       'DAU' as active_type,
       concat('ka','_',m1.effect_level) as active_group,
       1 as active_action,
       count(distinct m1.cid) as cnt
from retail.ofp_ka_info m1
    join retail.ofp_user_action_log m2 on m1.cid=m2.cid
    join retali_db.ba_user m3 on m3.cid=m1.cid
where m1.effect_level>0 and m2.created_at>=current_date
group by 1,2,3,4,5 order by 1,2,3,4,5
on duplicate key update active_cnt = cnt;

-- DAU ka in different channels
insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt)
-- DAU ka_market_source login
select date(m2.created_at) as calc_date,
       if(m3.rna_area = 'GLOBAL', 'CHINA', m3.rna_area) as rna_area,
       'DAU' as active_type,
       concat('ka','_',m3.market_source) as active_group,
       1 as active_action,
       count(distinct m1.cid) as cnt
from retail.ofp_ka_info m1
    join retail.ofp_user_action_log m2 on m1.cid=m2.cid
    join retali_db.ba_user m3 on m3.cid=m1.cid
where m1.effect_level>0 and m2.created_at>=current_date
group by 1,2,3,4,5 order by 1,2,3,4,5
on duplicate key update active_cnt = cnt;

-- DAU ka in different device
insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt)
-- DAU ka_device login
select date(m2.created_at) as calc_date,
       if(m3.rna_area = 'GLOBAL', 'CHINA', m3.rna_area) as rna_area,
       'DAU' as active_type,
       concat('ka','_',ifnull(m2.source_mark,'web')) as active_group,
       1 as active_action,
       count(distinct m1.cid) as cnt
from retail.ofp_ka_info m1
    join retail.ofp_user_action_log m2 on m1.cid=m2.cid
    join retali_db.ba_user m3 on m3.cid=m1.cid
where m1.effect_level>0 and m2.created_at>=current_date
group by 1,2,3,4,5 order by 1,2,3,4,5
on duplicate key update active_cnt = cnt;

-- DAU ka in trade_all type
insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt)
-- DAU ka trade_all
select order_end_dt as calc_date,
       if(rna_area = 'GLOBAL', 'CHINA', rna_area) as rna_area,
       'DAU' as active_type,
       'ka' as active_group,
       2 as active_action,
       count(distinct m1.cid) as cnt
from retail.ofp_ka_info m1
    join retali_db.ba_succ_transaction m2 on m1.cid=m2.cid
where m1.effect_level>0 and order_end_dt>=current_date
group by 1,2,3,4,5 order by 1,2,3,4,5
on duplicate key update active_cnt = cnt;

-- DAU ka in trade type
insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt)
-- DAU ka trade
select order_end_dt as calc_date,
       if(rna_area = 'GLOBAL', 'CHINA', rna_area) as rna_area,
       'DAU' as active_type,
       'ka' as active_group,
       3 as active_action,
       count(distinct m1.cid) as cnt
from retail.ofp_ka_info m1
    join retali_db.ba_succ_transaction m2 on m1.cid=m2.cid
where m1.effect_level>0 and order_end_dt>=current_date and m2.record_type in ('BUY','SELL')
group by 1,2,3,4,5 order by 1,2,3,4,5
on duplicate key update active_cnt = cnt;

-- DAU ka in using cards



-- ---------------------------------------------------------------

insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt)
-- MAU ka login
select date(m2.start_dt) as calc_date,
       if(m0.rna_area = 'GLOBAL', 'CHINA', m0.rna_area) as rna_area,
       'MAU' as active_type,
       'ka' as active_group,
       1 as active_action,
       count(distinct m1.cid) as cnt
from retail.ofp_ka_info m1 join (select cid,rna_area from retali_db.ba_user)m0 on m0.cid=m1.cid
join retail.ofp_user_action_log m3 on m1.cid = m3.cid
join (
    select a.register_time as start_dt, date(b.register_time) end_dt
    from (
          select distinct date(register_time) register_time
          from retali_db.ba_user
          where register_time >= current_date
      ) a
          join retali_db.ba_user b on a.register_time >= date(b.register_time) and a.register_time < date(b.register_time) + interval '30' day
    group by 1, 2
    order by 1, 2
) m2 on m2.end_dt = date(m3.created_at) -- =active date
where m1.effect_level>0
group by 1,2,3,4,5 order by 1,2,3,4,5
on duplicate key update active_cnt = cnt;


-- MAU ka
insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt)
-- MAU ka login
select date(current_date) as calc_date,
       if(m0.rna_area = 'GLOBAL', 'CHINA', m0.rna_area) as rna_area,
       'MAU' as active_type,
       'ka' as active_group,
       1 as active_action,
       count(distinct m1.cid) as cnt
from retail.ofp_ka_info m1 join (select cid,rna_area from retali_db.ba_user)m0 on m0.cid=m1.cid
join retail.ofp_user_action_log m3 on m1.cid = m3.cid
where m1.effect_level>0 and date(m3.created_at)>current_date-interval '30' day
group by 1,2,3,4,5 order by 1,2,3,4,5
on duplicate key update active_cnt = cnt;

-- MAU ka in different levels
insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt)
-- MAU ka_level login
select date(current_date) as calc_date,
       if(m0.rna_area = 'GLOBAL', 'CHINA', m0.rna_area) as rna_area,
       'MAU' as active_type,
       concat('ka','_',m1.effect_level) as active_group,
       1 as active_action,
       count(distinct m1.cid) as cnt
from retail.ofp_ka_info m1 join (select cid,rna_area from retali_db.ba_user)m0 on m0.cid=m1.cid
join retail.ofp_user_action_log m3 on m1.cid = m3.cid
where m1.effect_level>0 and date(m3.created_at)>current_date-interval '30' day
group by 1,2,3,4,5 order by 1,2,3,4,5
on duplicate key update active_cnt = cnt;


-- MAU ka in different channels
insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt)
-- MAU ka_market_source login
select date(current_date) as calc_date,
       if(m0.rna_area = 'GLOBAL', 'CHINA', m0.rna_area) as rna_area,
       'MAU' as active_type,
       concat('ka','_',m0.market_source) as active_group,
       1 as active_action,
       count(distinct m1.cid) as cnt
from retail.ofp_ka_info m1
join (select cid,rna_area,market_source from retali_db.ba_user)m0 on m0.cid=m1.cid
join retail.ofp_user_action_log m3 on m1.cid = m3.cid
where m1.effect_level>0 and date(m3.created_at)>current_date-interval '30' day
group by 1,2,3,4,5 order by 1,2,3,4,5
on duplicate key update active_cnt = cnt;

/*join (
    select a.register_time as start_dt, date(b.register_time) end_dt
    from (
          select distinct date(register_time) register_time
          from retali_db.ba_user
          where register_time >= current_date
      ) a
          join retali_db.ba_user b on a.register_time >= date(b.register_time) and a.register_time < date(b.register_time) + interval '30' day
    group by 1, 2
    order by 1, 2
) m2 on m2.end_dt = date(m3.created_at) -- =active date*/
-- 月活KA-不同终端
insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt)
-- MAU ka_market_source login
select date(current_date) as calc_date,
       if(m0.rna_area = 'GLOBAL', 'CHINA', m0.rna_area) as rna_area,
       'MAU' as active_type,
       concat('ka','_',ifnull(m3.source_mark,'web')) as active_group,
       1 as active_action,
       count(distinct m1.cid) as cnt
from retail.ofp_ka_info m1
join (select cid,rna_area from retali_db.ba_user)m0 on m0.cid=m1.cid
join retail.ofp_user_action_log m3 on m1.cid = m3.cid
where m1.effect_level>0 and date(m3.created_at)>current_date-interval '30' day
group by 1,2,3,4,5 order by 1,2,3,4,5
on duplicate key update active_cnt = cnt;

-- MAU ka in trade_all type
insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt)
-- MAU ka trade_all
select date(current_date) as calc_date,
       if(rna_area = 'GLOBAL', 'CHINA', rna_area) as rna_area,
       'MAU' as active_type,
       'ka' as active_group,
       2 as active_action,
       count(distinct m1.cid) as cnt
from retail.ofp_ka_info m1
    join retali_db.ba_succ_transaction m2 on m1.cid=m2.cid
where m1.effect_level>0 and order_end_dt>current_date-interval '30' day
group by 1,2,3,4,5 order by 1,2,3,4,5
on duplicate key update active_cnt = cnt;

-- MAU ka in trade type
insert into retali_db.ba_user_active_snap(calc_date, rna_area, active_type, active_group, active_action,active_cnt)
-- MAU ka trade
select date(current_date) as calc_date,
       if(rna_area = 'GLOBAL', 'CHINA', rna_area) as rna_area,
       'MAU' as active_type,
       'ka' as active_group,
       3 as active_action,
       count(distinct m1.cid) as cnt
from retail.ofp_ka_info m1
    join retali_db.ba_succ_transaction m2 on m1.cid=m2.cid
where m1.effect_level>0 and order_end_dt>current_date-interval '30' day and m2.record_type in ('BUY','SELL')
group by 1,2,3,4,5 order by 1,2,3,4,5
on duplicate key update active_cnt = cnt;


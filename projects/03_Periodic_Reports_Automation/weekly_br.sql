set @dt='2021-05-31';

-- 交易所周涨幅 
select a.period,a.exchange,round(a.amt,0) amt,round(b.amt,0) as last_week,round((a.amt - b.amt) / b.amt,5) as diff 
from 
(
	select 
	subdate(date(order_end_time),if(date_format(date(order_end_time),'%w')=0,7,date_format(date(order_end_time),'%w'))-1) as period,'novadax' exchange, -- 	date_format(order_end_time,'%Y-%m-01') period,
	sum(transaction_volume) as amt
	from bacc_nova.ba_dwd_success_transaction
	where order_type in ('Orderbook_Fiat_TX','Crypto_TX','Agent_Fiat_TX') 
	and order_end_time>=subdate(current_date,if(date_format(current_date,'%w')=0,7,date_format(current_date,'%w'))-1) - interval '14' day and order_end_dt<current_date and worth_coin='BRL'
	group by 1,2
	union all 
	select 
		subdate(date(traded_at),if(date_format(date(traded_at),'%w')=0,7,date_format(date(traded_at),'%w'))-1) as period,-- 		date_format(traded_at,'%Y-%m-01') period,
		exchange,
		sum(vol_value) as amt
	from novadax.nova_third_exchange_ticker
	where traded_at>=subdate(current_date,if(date_format(current_date,'%w')=0,7,date_format(current_date,'%w'))-1) - interval '14' day and traded_at<current_date 
	group by 1,2
)a 
left join 
(
	select subdate(date(order_end_time),if(date_format(date(order_end_time),'%w')=0,7,date_format(date(order_end_time),'%w'))-1) as period,'novadax' exchange,sum(transaction_volume) as amt
	from bacc_nova.ba_dwd_success_transaction
	where order_type in ('Orderbook_Fiat_TX','Crypto_TX','Agent_Fiat_TX') 
	and order_end_time>=subdate(current_date,if(date_format(current_date,'%w')=0,7,date_format(current_date,'%w'))-1) - interval '14' day and order_end_dt<current_date and worth_coin='BRL'
	group by 1,2
	union all 
	select 
		subdate(date(traded_at),if(date_format(date(traded_at),'%w')=0,7,date_format(date(traded_at),'%w'))-1) as period, -- 		date_format(traded_at,'%Y-%m-01') period,
		exchange,
		round(sum(vol_value),0) as amt
	from novadax.nova_third_exchange_ticker
	where traded_at>=subdate(current_date,if(date_format(current_date,'%w')=0,7,date_format(current_date,'%w'))-1) - interval '14' day and traded_at<current_date 
	group by 1,2
)b on a.exchange=b.exchange and a.period=b.period + interval '7' day 
order by 1 desc,2
;


-- 奖励金额 
select 
subdate(date(order_start_time),if(date_format(date(order_start_time),'%w')=0,7,date_format(date(order_start_time),'%w'))-1) as period,
award_note,
sum(amount_quote) as award_amt
from bacc_nova.ba_dwd_award
where kyc_area !='EUROPE' and award_note like '%trademap%' 
and order_end_time>=subdate(curdate(),if(date_format(curdate(),'%w')=0,7,date_format(curdate(),'%w'))-1) - interval '49' day and order_end_time<current_date
group by 1,2
union all 
select 
subdate(date(order_start_time),if(date_format(date(order_start_time),'%w')=0,7,date_format(date(order_start_time),'%w'))-1) as period,
'invited' as award_note,
sum(amount_quote) as award_amt
from bacc_nova.ba_dwd_award
where kyc_area !='EUROPE' and ifnull(award_note,'normal') not like '%trademap%' and award_type='Award_Fiat'
and order_end_time>=subdate(curdate(),if(date_format(curdate(),'%w')=0,7,date_format(curdate(),'%w'))-1) - interval '49' day and order_end_time<current_date
group by 1,2
union all 
select 
subdate(date(order_start_time),if(date_format(date(order_start_time),'%w')=0,7,date_format(date(order_start_time),'%w'))-1) as period,
'organic' as award_note,
sum(amount_quote) as award_amt
from bacc_nova.ba_dwd_award
where kyc_area !='EUROPE' and ifnull(award_note,'normal') not like '%trademap%' and award_type='Award_Crypto'
and order_end_time>=subdate(curdate(),if(date_format(curdate(),'%w')=0,7,date_format(curdate(),'%w'))-1) - interval '49' day and order_end_time<current_date
group by 1,2
order by 1 desc,2
;

-- 周报overview_monthly register channel
select date_format(order_start_time,'%Y-%m-01') as period,award_note,sum(amount_quote) as award_amt
from bacc_nova.ba_dwd_award
where kyc_area !='EUROPE' and award_note like '%trademap%' and order_end_time>=date_format(current_date,'%Y-%m-01') - interval '5' month and order_end_time<current_date
group by 1,2
union all 
select date_format(order_start_time,'%Y-%m-01') as period,'invited' as award_note,sum(amount_quote) as award_amt
from bacc_nova.ba_dwd_award
where kyc_area !='EUROPE' and ifnull(award_note,'normal') not like '%trademap%' and award_type='Award_Fiat' 
and order_end_time>=date_format(current_date,'%Y-%m-01') - interval '5' month and order_end_time<current_date
group by 1,2
union all 
select date_format(order_start_time,'%Y-%m-01') as period,'organic' as award_note,sum(amount_quote) as award_amt
from bacc_nova.ba_dwd_award
where kyc_area !='EUROPE' and ifnull(award_note,'normal') not like '%trademap%' and award_type='Award_Crypto' 
and order_end_time>=date_format(current_date,'%Y-%m-01') - interval '5' month and order_end_time<current_date
group by 1,2
order by 1 desc,2
;



-- 价格波动 
select 
	subdate(settle_date,if(date_format(settle_date,'%w')=0,7,date_format(settle_date,'%w'))-1) as period,
	concat(digital_code,'_',legal_code) as symbol,
	round(sum(price)/count(DISTINCT settle_date),4) as avg_price,
	round(min(price),4) as min_price,
	round(max(price),4) as max_price,
	round((max(price)-min(price))/min(price),4) as min_max_price_diff
from bacc_nova.dim_exchange_rate
where settle_date>=subdate(curdate(),if(date_format(curdate(),'%w')=0,7,date_format(curdate(),'%w'))-1) - interval '7' day and settle_date<current_date and legal_code='BRL'
group by 1,2
order by 1,6 desc 
;




## KOL 邀请情况
select 
	subdate(date(m1.register_time),if(date_format(date(m1.register_time),'%w')=0,7,date_format(date(m1.register_time),'%w'))-1) as period
-- 	, ifnull(m3.email,m11.origin_source)
	, count(DISTINCT m1.cid) Youtube_KOL_register
	, count(DISTINCT if(ifnull(m3.email,m11.origin_source)='marcelcolchesqui@hotmail.com',m1.cid,null)) as marcelcolchesqui
	, count(DISTINCT if(ifnull(m3.email,m11.origin_source)='cryptotchaps@outlook.com',m1.cid,null)) as cryptotchaps 
	, count(DISTINCT if(ifnull(m3.email,m11.origin_source)='siterendamaior@gmail.com',m1.cid,null)) as siterendamaior 
	, count(DISTINCT if(ifnull(m3.email,m11.origin_source) in ('cryptotchaps@outlook.com','marcelcolchesqui@hotmail.com','siterendamaior@gmail.com'),m1.cid,null))/count(DISTINCT m1.cid) as above_3
	, count(DISTINCT if(ifnull(m3.email,m11.origin_source) not in ('cryptotchaps@outlook.com','marcelcolchesqui@hotmail.com','siterendamaior@gmail.com'),m1.cid,null)) as other 
from bacc_nova.ba_dwd_customer m1 
left join bacc_nova.ba_dwp_register_source m11 on m11.cid=m1.cid 
left join novadax.nova_customer_invitation m2 on m2.invitee_id=m1.cid and m2.invitee_id !=m2.inviter_id
left join bacc_nova.dim_youtuber_list m3 on m3.cid=m2.inviter_id 
where m1.register_time>=@dt and m1.register_time<current_date and m1.market_source='Youtube_KOL' and m1.kyc_area !='EUROPE' 
group by 1
;

-- invited 渠道
set @dt='2021-06-07';
select 
	subdate(date(m1.register_time),if(date_format(date(m1.register_time),'%w')=0,7,date_format(date(m1.register_time),'%w'))-1) as period
	, count(DISTINCT m1.cid) invited_register 
	, count(DISTINCT m2.inviter_id) inviter 
	, count(DISTINCT m1.cid)/count(DISTINCT m2.inviter_id) avg_invitee_inviter
	, count(DISTINCT if(m1.current_kyc_level>0,m1.cid,null)) as kyc 
	, count(DISTINCT if(m1.is_try_deposit=1,m1.cid,null)) as try_deposit 
from bacc_nova.ba_dwd_customer m1 
left join novadax.nova_customer_invitation m2 on m2.invitee_id=m1.cid and m2.invitee_id !=m2.inviter_id
left join novadax.nova_customer m21 on m21.id=m2.inviter_id
where m1.register_time>=@dt and m1.register_time<current_date and m1.market_source='invited' and m1.register_time>='2020-06-08' and m1.kyc_area !='EUROPE'
group by 1
;

-- top invited 用户 
set @dt='2021-06-07';
select 
	subdate(date(m1.register_time),
	if(date_format(date(m1.register_time),'%w')=0,7,
	date_format(date(m1.register_time),'%w'))-1) as period
	, m2.inviter_id
	, m21.name
	, count(DISTINCT m1.cid) invited_register 
from bacc_nova.ba_dwd_customer m1 
left join novadax.nova_customer_invitation m2 on m2.invitee_id=m1.cid and m2.invitee_id !=m2.inviter_id
left join novadax.nova_customer m21 on m21.id=m2.inviter_id
where m1.register_time>=@dt 
	and m1.register_time<current_date 
	and m1.market_source='invited' 
	and m1.register_time>='2020-06-08' 
	and m1.kyc_area !='EUROPE'
group by 1,2 
order by 1 desc,4 desc;

-- 注册后首次提交存款订单
select 
	case
		when timestampdiff(day,date(m1.created_at),date(m2.min_deposit_time))<=1 then '<=1'
		when timestampdiff(day,date(m1.created_at),date(m2.min_deposit_time)) between 2 and 7 then '[2,7]'
		when timestampdiff(day,date(m1.created_at),date(m2.min_deposit_time)) between 8 and 30 then '[8,30]'
		else '>30'
	end as diff,
	count(DISTINCT m1.id)
from novadax.nova_customer m1 
join 
(
	select customer_id,min(min_deposit_time) min_deposit_time
	from 
	(
		select customer_id,min(created_at) min_deposit_time from novadax.nova_legal_record where record_note != 'OTC' and record_type='DEPOSIT' and asset_code='BRL' group by 1
		union all 
		select m1.customer_id,min(m1.created_at) min_deposit_time 
		from novadax.nova_digital_record m1 
		join novadax.nova_customer m2 on m1.customer_id=m2.id
		where is_test=0 and m1.record_note != 'OTC' and m1.record_type='COIN_IN' and m2.kyc_area !='EUROPE'
		group by 1
	)a
	group by 1 
)m2 on m1.id=m2.customer_id
where m1.is_test=0 and m1.kyc_area !='EUROPE'
group by 1 with rollup
;

-- 落地页薅羊毛 
select -- DISTINCT m1.*,m2.order_id,m2.amount,m2.amount_in_brl,m2.order_start_time as award_time,m3.cid as out_cid 
	subdate(date(m2.order_start_time),if(date_format(m2.order_start_time,'%w')=0,7,date_format(m2.order_start_time,'%w'))-1) as period,
	count(DISTINCT m1.customer_id) as activity_user,
	count(DISTINCT m2.cid) as award_user,
	count(DISTINCT m3.cid) as out_user_30h,
	count(DISTINCT m3.cid)/count(DISTINCT m2.cid) as out_rate 
from 
(
	select m1.id,m1.customer_id,m1.reward_quantity,m1.reward_unit,m1.created_at,m2.source
	from novadax.nova_customer_activity_reward m1
	join novadax.nova_customer_ext m2 on m1.customer_id=m2.customer_id 
	where m2.source !='TEST' and m1.activity_code='googleReward'
)m1
left join bacc_nova.ba_dwd_award m2 on date(m1.created_at)=date(m2.order_start_time) and m1.customer_id=m2.cid and upper(m1.reward_unit)=m2.currency and m2.order_id != '2_LR715036936498065408'
left join bacc_nova.ba_dwd_success_transaction m3 on m3.cid=m2.cid and (m3.order_start_time between m2.order_start_time + interval '1' minute and m2.order_start_time + interval '30' hour)
	and m3.is_otc != 'OTC' and m3.record_type in ('WITHDRAW','COIN_OUT')
-- where m3.cid is not null 
group by 1

-- 首存转化率-失败原因比例 
select 
	period,
	register_device_type,
	count(DISTINCT cid) min_try_deposit,
	count(DISTINCT if(min_try_deposit_fiat=1,cid,null))/count(DISTINCT cid) min_try_deposit_fiat_pct,
	count(DISTINCT if(min_try_deposit_crypto=1,cid,null))/count(DISTINCT cid) min_try_deposit_crypto_pct,
	count(DISTINCT if(deposit_succ=1,cid,null)) deposit_succ,
	count(DISTINCT if(deposit_succ=0 and latest='FAIL',cid,null)) deposit_fail,
	count(DISTINCT if(deposit_succ=0 and latest='FAIL' and latest_reason like '%machine-failed%',cid,null))/count(DISTINCT if(deposit_succ=0 and latest='FAIL',cid,null)) deposit_fail_machine_pct,
	count(DISTINCT if(deposit_succ=0 and latest !='FAIL',cid,null)) pending,
	count(DISTINCT if(deposit_succ=1,cid,null))/count(DISTINCT cid) succ_pct,
	count(DISTINCT if(deposit_succ=0 and latest='FAIL',cid,null))/count(DISTINCT cid) fail_pct,
	count(DISTINCT if(deposit_succ=0 and latest !='FAIL',cid,null))/count(DISTINCT cid) pending_pct
from 
(
	select 
		subdate(date(m1.register_time),if(date_format(date(m1.register_time),'%w')=0,7,date_format(date(m1.register_time),'%w'))-1) as period,
		m1.register_device_type,
		m1.cid,
		count(DISTINCT if(week(m1.register_time,1)=week(m1.min_try_deposit_time,1),m1.cid,null)) min_try_deposit,
		count(DISTINCT if(m2.rnk=1 and m2.record_type='DEPOSIT',m1.cid,null)) min_try_deposit_fiat,
		count(DISTINCT if(m2.rnk=1 and m2.record_type='COIN_IN',m1.cid,null)) min_try_deposit_crypto,
		count(DISTINCT if(week(m1.register_time,1)=week(m1.min_deposit_time,1),m1.cid,null)) deposit_succ,
		group_concat(m2.rnk,'_',m2.record_status,'_',record_note) detail,
		substring_index(group_concat(m2.rnk,'_',m2.record_status),concat(count(DISTINCT m2.id),'_'),-1) latest,
		substring_index(group_concat(m2.rnk,'_',m2.record_note),concat(count(DISTINCT m2.id),'_'),-1) latest_reason 
	from bacc_nova.ba_dwd_customer m1
	join 
	(
		select a.*,if(@cid=customer_id,@rnk:= @rnk + 1,@rnk :=1)rnk,@cid :=customer_id
		from 
		(
			select DISTINCT customer_id,created_at,id,record_status,record_note,record_type,finished_at from novadax.nova_legal_record where record_note != 'OTC' and record_type='DEPOSIT' and asset_code='BRL' 
			union all 
			select DISTINCT m1.customer_id,m1.created_at,m1.id,m1.record_status,record_note,record_type,finished_at
			from novadax.nova_digital_record m1 
			join novadax.nova_customer m2 on m1.customer_id=m2.id
			where is_test=0 and m1.record_note != 'OTC' and m1.record_type='COIN_IN' and m2.kyc_area !='EUROPE'
			order by 1,2 
		)a join (select @rnk:='',@cid:='')b 
	)m2 on m1.cid=m2.customer_id 
	where m1.kyc_area ='BRAZIL' and m1.kyc_type='INDIVIDUAL' 
		and m1.register_time>=subdate(curdate(),if(date_format(curdate(),'%w')=0,7,date_format(curdate(),'%w'))-1) - interval '7' day 
		and m1.register_time<current_date 
		and subdate(date(register_time),if(date_format(date(register_time),'%w')=0,7,date_format(date(register_time),'%w'))-1)=subdate(date(min_try_deposit_time),if(date_format(date(min_try_deposit_time),'%w')=0,7,date_format(date(min_try_deposit_time),'%w'))-1)
		and m2.created_at>=subdate(curdate(),if(date_format(curdate(),'%w')=0,7,date_format(curdate(),'%w'))-1) - interval '7' day 
		and m2.created_at<current_date
	group by 1,2,3
)temp 
group by 1,2
;
// 找出两个地址之间所有交易记录。ps这里的节点地址'0xbD0da18F1e4B4DbF0a3533Ce605a62BBEc99804F'是选取的下面这个查询的第一个三角形的中上和左下节点，为什么它俩之间明明在下面这个查询结果里显示他俩来来回回总共有三笔交易，但是在此查询框的收出结果里只显示了两笔交易，是因为你仔细看下面这个查询，他显示的三个箭头是两个交易方向的总和，而此查询框的代码的查询逻辑指示，查询前者节点向后者节点方向去的交易记录，也就是说下面这个查询框是双向统计，而此查询框是单项统计如果你在此查询框的代码中调换前后者节点地址，就会显示逆向只有一条的交易结果

MATCH (a:Address {address: '0x35c9a4dae1ff05788f24b5b32721d89340cbb636'})-[r:TRANSFER_TO]->(b:Address {address: '0x0889e9327b98d7d1be3c301a4585ff3330502c9a'})
RETURN toFloat(r.value), r.hash, r.block_number
ORDER BY r.block_number

// MATCH (a:Address {address: 'A'})-[r:TRANSFER_TO]->(b:Address {address: 'B'})
// RETURN r.value, r.hash, r.block_number

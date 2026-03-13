## 常用查询模式

### 查询在售商品基本信息
```sql
SELECT wareId, title, brandName, jdPrice, stockNum
FROM jd_{shopId}_wares
WHERE wareStatus = 8
ORDER BY updateTime DESC
LIMIT 100
```

### 查询商品评分分布
```sql
SELECT
    score,
    count() AS cnt,
    round(cnt / sum(cnt) OVER () * 100, 1) AS pct
FROM jd_{shopId}_comments
WHERE sku_id = {wareId}
GROUP BY score
ORDER BY score DESC
```

### 查询差评内容（用于分析）
```sql
SELECT content, score, create_time, useful_count
FROM jd_{shopId}_comments
WHERE sku_id = {wareId} AND score <= 2
ORDER BY useful_count DESC, create_time DESC
LIMIT 50
```

### 查询有图评价
```sql
SELECT content, score, images_json, create_time
FROM jd_{shopId}_comments
WHERE sku_id = {wareId} AND has_image = 1 AND imiage_status = 1
ORDER BY create_time DESC
LIMIT 20
```

### 查询商品热门问答
```sql
SELECT
    question_content,
    total_answer,
    groupArray(answer_content) AS answers
FROM jd_{shopId}_qa
WHERE item_id = toString({wareId})
GROUP BY question_id, question_content, total_answer
ORDER BY total_answer DESC
LIMIT 10
```

### 商品评论+问答综合分析
```sql
-- 先查评论概况
SELECT
    count() AS total_comments,
    round(avg(score), 2) AS avg_score,
    countIf(score >= 4) AS good_cnt,
    countIf(score <= 2) AS bad_cnt,
    countIf(has_image = 1) AS with_image_cnt
FROM jd_{shopId}_comments
WHERE sku_id = {wareId};

-- 再查问答概况
SELECT
    count(DISTINCT question_id) AS total_questions,
    count() AS total_answers
FROM jd_{shopId}_qa
WHERE item_id = toString({wareId});
```

### 品牌维度分析
```sql
SELECT
    w.brandName,
    count(DISTINCT w.wareId) AS ware_count,
    round(avg(w.jdPrice), 2) AS avg_price,
    round(avg(c.avg_score), 2) AS avg_rating
FROM jd_{shopId}_wares w
LEFT JOIN (
    SELECT sku_id, avg(score) AS avg_score
    FROM jd_{shopId}_comments
    GROUP BY sku_id
) c ON w.wareId = c.sku_id
WHERE w.wareStatus = 8
GROUP BY w.brandName
ORDER BY ware_count DESC
LIMIT 20
```

---

## 关键注意事项

1. **表名中的 shopId**: `jd_1000000266_wares` 中 `1000000266` 是店铺ID，不同店铺对应不同表
2. **wares ↔ comments 关联**: `wares.wareId = comments.sku_id`（Int64 直接匹配）
3. **wares ↔ qa 关联**: `toString(wares.wareId) = qa.item_id`（注意类型转换，qa.item_id 是 String）
4. **评论 TTL**: comments 表数据保留 365 天后自动清理
5. **qa 表结构**: 一行 = 一个回答，查问题要 GROUP BY question_id
6. **wareStatus 过滤**: 只有 `wareStatus = 8` 才是在售商品
7. **晒单图片过滤**: `has_image = 1 AND imiage_status = 1` 才是通过审核的晒单图
8. **字段拼写**: 注意 `imiage_status` 不是 `image_status`（表结构原始拼写）
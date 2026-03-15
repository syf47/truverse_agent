---
name: jd-clickhouse-schema
description: >
  京东电商 ClickHouse 数据库表结构。包含商品表(wares)、评论表(comments)、问答表(qa)
  三张核心表的完整字段定义、关联关系、分区策略和常用查询模式。
  当 Agent 需要构造 SQL 查询、分析商品数据、评论数据、问答数据时使用。
tags:
  - 商品
  - 评论
  - 问答
  - 查询
  - SQL
  - ClickHouse
  - SKU
  - SPU
  - 评分
  - 评价
  - 价格
  - 品牌
  - 类目
  - 库存
  - wareId
  - sku_id
  - comment
  - wares
  - 表结构
  - 数据库
  - 晒单
  - 回复
  - 提问
  - 回答
---

# 京东电商 ClickHouse 数据库表结构

> 表名中的 `1000000266` 是店铺 ID（shopId），实际使用时按需替换。

---

## 表关联关系

```
jd_{shopId}_wares (商品表)
    │
    ├── wareId ←→ sku_id (jd_{shopId}_comments.sku_id = wares.wareId)
    │   一个商品有多条评论
    │
    └── toString(wareId) ←→ item_id (jd_{shopId}_qa.item_id = toString(wares.wareId))
        一个商品有多条问答

jd_{shopId}_comments (评论表)
    │
    └── sku_id ←→ item_id (toString(comments.sku_id) = qa.item_id)
        评论和问答通过商品ID关联

jd_{shopId}_qa (问答表)
    每行存储一条回答，问题信息冗余存储（同一 question_id 多行 = 多个回答）
```

---

## 1. jd_{shopId}_wares — 京东商品数据表

**引擎**: MergeTree
**分区**: toYYYYMM(createTime)
**排序键**: (wareId, updateTime)

### 核心字段

| 字段 | 类型 | 说明 |
|------|------|------|
| wareId | Int64 | **主键** 商品ID |
| title | String | 商品标题 |
| spuId | Int64 | 标品ID |
| categoryId | Int32 | 3级类目ID |
| categorySecId | Int32 | 2级类目ID |
| multiCategoryId | Int32 | 末级类目ID |
| brandId | Int32 | 品牌ID |
| brandName | String | 品牌名称 |
| shopId | Int64 | 商家shopID |

### 价格与库存

| 字段 | 类型 | 说明 |
|------|------|------|
| jdPrice | Decimal(10,2) | 京东价（元） |
| marketPrice | Decimal(10,2) | 市场价（元） |
| costPrice | Decimal(10,2) | 成本价（元） |
| stockNum | Int32 | 总库存数 |

### 商品状态

| 字段 | 类型 | 说明 |
|------|------|------|
| wareStatus | Int8 | -1:删除 1:从未上架 2:自主下架 4:系统下架 **8:上架** |
| colType | Int8 | 合作模式（0:SOP 1:FBP 2:LBP 等） |

### 商品详情

| 字段 | 类型 | 说明 |
|------|------|------|
| itemNum | String | 商品货号 |
| outerId | String | 商家外部ID |
| barCode | String | 商品条形码 |
| logo | String | 商品主图URL（完整https路径） |
| imagesJson | String | 商品图片JSON |
| sellPoint | String | 卖点 |
| introduction | String | PC端商详 |
| mobileDesc | String | 移动端商详 |
| delivery | String | 发货地 |
| wrap | String | 包装规格 |
| packListing | String | 包装清单 |

### 物流属性

| 字段 | 类型 | 说明 |
|------|------|------|
| weight | Float32 | 重量 |
| width | Float32 | 宽度 |
| height | Float32 | 高度 |
| length | Float32 | 长度 |
| transportId | Int64 | 运费模板ID |

### 扩展属性（JSON/Array 字段）

| 字段 | 类型 | 说明 |
|------|------|------|
| shopCategorys | Array(Int32) | 店内分类ID数组 |
| shopCategorysJson | String | 店内分类JSON |
| featuresJson | String | 商品特殊属性JSON |
| multiCatePropsJson | String | 四级类目属性JSON |
| adWordsJson | String | 广告词JSON |

### OCR 结果

| 字段 | 类型 | 说明 |
|------|------|------|
| itemImgsJson_result | String | 商品图片OCR结果JSON |
| mobileDesc_ocr_result | String | 移动端商详图片OCR结果JSON |
| mobileDesc_result | String | mobileDesc提取的图片URL数组JSON |

### 时间字段

| 字段 | 类型 | 说明 |
|------|------|------|
| created | DateTime | 商品创建时间 |
| modified | DateTime | 最后修改时间 |
| onlineTime | DateTime | 最后上架时间 |
| offlineTime | DateTime | 最后下架时间 |
| updateTime | DateTime | 数据更新时间 |
| createTime | DateTime | 入库时间 |

---

## 2. jd_{shopId}_comments — 京东商品评价表

**引擎**: MergeTree
**分区**: toYYYYMM(create_time)
**排序键**: (sku_id, create_time, comment_id)
**TTL**: create_time + 365天

### 核心字段

| 字段 | 类型 | 说明 |
|------|------|------|
| comment_id | String | **主键** 评论ID |
| sku_id | Int64 | SKU ID（关联 wares.wareId） |
| sku_name | String | 商品名称 |
| sku_image | String | 商品图片URL |
| score | Int8 | 评分 1-5（1:非常差 2:差 3:一般 4:好 5:非常好） |
| content | String | 评论内容 |
| create_time | DateTime | 评论时间 |

### 图片相关

| 字段 | 类型 | 说明 |
|------|------|------|
| has_image | Int8 | 是否有图 0/1 |
| image_count | Int8 | 图片数量 |
| images_json | String | 图片列表JSON |
| imiage_status | Int8 | 晒单审核状态 -1:不通过(删除) 1:通过 2:审核中 |

### 互动数据

| 字段 | 类型 | 说明 |
|------|------|------|
| is_vendor_reply | Int8 | 是否商家回复 0/1 |
| reply_count | Int16 | 回复数 |
| reply_id | Nullable(Int64) | 回复ID |
| replies_json | String | 回复列表JSON |
| useful_count | Int32 | 有用数（点赞数） |

### 用户信息

| 字段 | 类型 | 说明 |
|------|------|------|
| nick_name | String | 用户昵称 |
| buyer_pin | String | 用户标识（脱敏） |
| open_id_buyer | String | 买家openId |
| xid_buyer | String | 买家xid |
| encrypt_order_id | String | 订单ID（加密） |
| status | Int8 | 评论状态 |
| ingest_time | DateTime | 入库时间 |

---

## 3. jd_{shopId}_qa — 京东商品用户问答表

**引擎**: MergeTree
**分区**: toYYYYMM(question_time)
**排序键**: (item_id, question_id, answer_id)

> **重要**: 每行存储一条**回答**，问题信息冗余存储。同一 question_id 可能有多行（多个回答）。

### 问题字段

| 字段 | 类型 | 说明 |
|------|------|------|
| item_id | String | 商品ID（关联 toString(wares.wareId)） |
| question_id | String | 问题ID（cluster_id） |
| question_content | String | 问题内容 |
| question_url | String | 问题详情页链接 |
| total_answer | Int32 | 该问题的回答总数 |
| question_time | DateTime | 提问时间 |

### 回答字段

| 字段 | 类型 | 说明 |
|------|------|------|
| answer_id | String | 回答ID |
| answer_content | String | 回答内容 |
| answer_time | DateTime | 回答时间 |
| answer_nick | String | 回答者昵称 |
| answer_location | String | 回答者地区 |
| ingest_time | DateTime | 入库时间 |

---

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

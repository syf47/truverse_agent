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
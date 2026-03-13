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
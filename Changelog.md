
AASND
-----

AAS WMS MES


2017-08-02 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; v1.0
----------------------------------------------------------------
- 采购收货；从Oracle中导入采购订单，生成采购收货单确认后提交质量部门检测，检测完成后仓库上架入库
- 销售发货；从Oracle中导入销售发票，生成销售发货单确认后仓库拣货出库
- 仓库收货；仓库按标签方式扫码收货，上架确认入库，更新库存
- 仓库发货；根据发货请求，按照先进先出原则生成拣货清单，仓库人员直接根据拣货清单直接拣货出库
- 生产领料；产线根据实际需求，填写领料单确认后，仓库人员根据需求进行发货出库
- 质量检测；采购收货之后提交报检，QC根据实际情况检测，如果标签中只有部分合格，需要将不合格品拆分出来重新打印标签，交由仓库处理
- 移动现场；使用平板借助微信企业号平台，帮助仓库人员实现仓库收发货操作


2017-08-24 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; v1.1
----------------------------------------------------------------
- 员工管理；添加员工记录以及员工出勤记录
- 设备管理；从redis里中抓取MDC设备数据保存到Odoo中
- 生产管理；添加产线、工位、出勤记录，MES基础数据管理
- 临时版本；此版本只做临时记录，不可在实际中使用，需求有变化


2017-09-06 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; v1.2
----------------------------------------------------------------
- 设备数据；工控机采集的数据推入Redis,系统从Redis抓取工控机设备数据并保存
- 设备管理；设备添加看板视图，添加状态颜色区分，设备分为扫描设备和工控设备，工控设备会自动采集设备运行数据
- 生产管理；添加产线、工位、出勤记录，MES基础数据管理
- 员工管理；添加条码枪扫描上岗控制，实时查看员工状态

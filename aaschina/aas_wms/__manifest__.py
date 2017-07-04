# -*- coding: utf-8 -*-

{
    'name': u'安费诺仓库管理',
    'version': '1.0',
    'category': 'Zhiq Amphenol',
    'sequence': 2,
    'summary': u'安费诺仓库管理',
    'description': """
        安费诺仓库管理
    """,
    'author': 'Luforn',
    'website': 'http://www.zhiq.info',
    'depends': ['stock', 'aas_base'],
    'data': [
        'data/aas_wms_data.xml',
        'data/aas_wms_sequence.xml',
        'security/ir.model.access.csv',
        'views/aas_stock_models_view.xml',
        'views/aas_product_label_view.xml',
        'views/aas_receive_deliver_view.xml',
        'views/aas_stock_receipt_view.xml',
        'views/aas_stock_receipt_inside_view.xml',
        'views/aas_stock_receipt_outside_view.xml',
        'wizard/aas_stock_receipt_wizard_view.xml',
        'views/aas_stock_delivery_view.xml',
        'views/aas_stock_delivery_outside_view.xml',
        'views/aas_stock_delivery_inside_view.xml',
        'wizard/aas_stock_delivery_wizard_view.xm'
    ],
    'qweb':[],
    'installable': True,
    'application': True,
    'auto_install': False
}

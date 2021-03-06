/**
 * Created by luforn on 2017-7-14.
 */

mui.init({
    swipeBack:true,
    pullRefresh: {
        container: '#delivery_detail_pullrefresh',
        down : {
          height:50,
          auto: false,
          contentdown : "下拉可以刷新",
          contentover : "释放立即刷新",
          contentrefresh : "正在刷新...",
          callback : function(){ mui.later(function(){ window.location.reload(true); }, 1000); }
        }
    }
});


mui.ready(function(){

    //加载动画
    function aas_delivery_detail_loading(){
        var deliverymask = mui.createMask();
        var loadimg = document.createElement('img'), maskEl = deliverymask[0];
        maskEl.removeEventListener('tap', arguments.callee);
        loadimg.setAttribute('src', '/aas_base/static/wechat/aas/images/loading.gif');
        loadimg.setAttribute('width', '50px');
        loadimg.setAttribute('height', '50px');
        loadimg.setAttribute('alt', '加载中.........');
        loadimg.setAttribute('style', "position:fixed;top:50%;left:50%;margin:-25px 0 0 -25px;");
        maskEl.appendChild(loadimg);
        deliverymask.show();
        return deliverymask;
    }

    var access_url = location.href;
    mui.ajax('/aaswechat/wms/scaninit',{
        data: JSON.stringify({
            jsonrpc: "2.0", method: 'call', params: {'access_url': access_url}, id: Math.floor(Math.random() * 1000 * 1000 * 1000)
        }),
        dataType:'json', type:'post', timeout:10000,
        headers:{'Content-Type':'application/json'},
        success:function(data){
            wx.config(data.result);
            wx.ready(function(){});
            wx.error(function(res){});
        },
        error:function(xhr,type,errorThrown){ console.log(type); }
    });

    //扫描标签
    document.getElementById('action_scan_label').addEventListener('tap', function(){
        wx.scanQRCode({
            needResult: 1,
            desc: '扫描标签',
            scanType: ["qrCode"],
            success: function (result) {
                var access_id = Math.floor(Math.random() * 1000 * 1000 * 1000);
                var deliveryid = parseInt(document.getElementById('delivery_detail_pullrefresh').getAttribute('deliveryid'));
                var params = {'barcode': result.resultStr, 'delivery_id': deliveryid};
                mui.ajax('/aaswechat/wms/deliverylabelscan',{
                    data: JSON.stringify({ jsonrpc: "2.0", method: 'call', params: params, id: access_id }),
                    dataType:'json', type:'post', timeout:10000,
                    headers:{'Content-Type':'application/json'},
                    success:function(data){
                        var dresult = data.result;
                        if (!dresult.success){
                            mui.toast(dresult.message);
                            return ;
                        }
                        var delivery_operations = document.getElementById('delivery_operations');
                        var operationli = document.createElement('li');
                        operationli.className = 'mui-table-view-cell';
                        operationli.setAttribute('operationid', dresult.operation_id);
                        operationli.innerHTML = '<div class="mui-slider-right mui-disabled"><a class="mui-btn mui-btn-red">删除</a></div>' +
                            '<div class="mui-slider-handle">' +
                                '<div class="mui-table"> ' +
                                    '<div class="mui-table-cell mui-col-xs-8 mui-text-left">'+dresult.product_code+'</div>' +
                                    '<div class="mui-table-cell mui-col-xs-4 mui-text-right">'+dresult.product_qty+'</div>'+
                                '</div>' +
                                '<div class="mui-table"> ' +
                                    '<div class="mui-table-cell mui-col-xs-8 mui-text-left">'+dresult.label_name+'</div>' +
                                    '<div class="mui-table-cell mui-col-xs-4 mui-text-right">'+dresult.location_name+'</div>'+
                                '</div>' +
                            '</div>';
                        delivery_operations.appendChild(operationli);
                        document.getElementById('delivery_picking_qty').innerHTML = dresult.picking_qty;
                    },
                    error:function(xhr,type,errorThrown){
                        console.log(type);
                    }
                });
            },
            fail: function(result){  mui.toast(result.errMsg); }
        });
    });

    //删除发货作业
    var delivery_delete_flag = false;
    mui('#delivery_operations').on('tap', '.mui-btn', function(event) {
        if(delivery_delete_flag){
            mui.toast('删除操作正在处理，请耐心等待！');
            return ;
        }
        delivery_delete_flag = true;
        var li = this.parentNode.parentNode;
        mui.confirm('确认删除该条记录？', '清除上架', ['确认', '取消'], function(e) {
            if(e.index!=0){
                delivery_delete_flag = false;
                mui.swipeoutClose(li);
                return ;
            }
            var operation_id = parseInt(li.getAttribute('operationid'));
            var access_id = Math.floor(Math.random() * 1000 * 1000 * 1000);
            var delivery_delmask = aas_delivery_detail_loading();
            mui.ajax('/aaswechat/wms/deliverydeloperation',{
                data: JSON.stringify({ jsonrpc: "2.0", method: 'call', params: {'operation_id': operation_id}, id: access_id }),
                dataType:'json', type:'post', timeout:10000,
                headers:{'Content-Type':'application/json'},
                success:function(data){
                    var dresult = data.result;
                    delivery_delete_flag = false;
                    delivery_delmask.close();
                    if (!dresult.success){
                        mui.toast(dresult.message);
                        return ;
                    }
                    document.getElementById('delivery_operations').removeChild(li);
                    window.location.reload(true);
                },
                error:function(xhr,type,errorThrown){
                    console.log(type);
                    delivery_delete_flag = false;
                    delivery_delmask.close();
                }
            });
        });
    });

    //计算拣货清单
    var delivery_picking_flag = false;
    document.getElementById('action_picking_list').addEventListener('tap', function(){
        if (delivery_picking_flag){
            mui.toast('操作正在处理中，请耐心等待！');
            return ;
        }
        delivery_picking_flag = true;
        var access_id = Math.floor(Math.random() * 1000 * 1000 * 1000);
        var deliveryid = parseInt(document.getElementById('delivery_detail_pullrefresh').getAttribute('deliveryid'));
        var params = {'delivery_id': deliveryid};
        var deliverymask = aas_delivery_detail_loading();
        mui.ajax('/aaswechat/wms/deliverypickinglist',{
            data: JSON.stringify({ jsonrpc: "2.0", method: 'call', params: params, id: access_id }),
            dataType:'json', type:'post', timeout:20000,
            headers:{'Content-Type':'application/json'},
            success:function(data){
                delivery_picking_flag = false;
                deliverymask.close();
                var dresult = data.result;
                if (!dresult.success){
                    mui.toast(dresult.message);
                    return ;
                }
                window.location.reload(true);
            },
            error:function(xhr,type,errorThrown){
                delivery_picking_flag = false;
                deliverymask.close();
                console.log(type);
            }
        });
    });


    //确认拣货
    var delivery_pickconfirm_flag = false;
    document.getElementById('action_pick_confirm').addEventListener('tap', function(){
        if (delivery_pickconfirm_flag){
            mui.toast('操作正在处理中，请耐心等待！');
            return ;
        }
        delivery_pickconfirm_flag = true;
        var access_id = Math.floor(Math.random() * 1000 * 1000 * 1000);
        var deliveryid = parseInt(document.getElementById('delivery_detail_pullrefresh').getAttribute('deliveryid'));
        var params = {'delivery_id': deliveryid};
        var deliverymask = aas_delivery_detail_loading();
        mui.ajax('/aaswechat/wms/deliverypickconfirm',{
            data: JSON.stringify({ jsonrpc: "2.0", method: 'call', params: params, id: access_id }),
            dataType:'json', type:'post', timeout:20000,
            headers:{'Content-Type':'application/json'},
            success:function(data){
                delivery_pickconfirm_flag = false;
                deliverymask.close();
                var dresult = data.result;
                if (!dresult.success){
                    mui.toast(dresult.message);
                    return ;
                }
                window.location.reload(true);
            },
            error:function(xhr,type,errorThrown){
                delivery_pickconfirm_flag = false;
                deliverymask.close();
                console.log(type);
            }
        });
    });

    //执行发货
    var delivery_pickdone_flag = false;
    document.getElementById('action_delivery_done').addEventListener('tap', function(){
        if (delivery_pickdone_flag){
            mui.toast('操作正在处理中，请耐心等待！');
            return ;
        }
        delivery_pickdone_flag = true;
        var access_id = Math.floor(Math.random() * 1000 * 1000 * 1000);
        var deliveryid = parseInt(document.getElementById('delivery_detail_pullrefresh').getAttribute('deliveryid'));
        var params = {'delivery_id': deliveryid};
        var deliverymask = aas_delivery_detail_loading();
        mui.ajax('/aaswechat/wms/deliverypickdone',{
            data: JSON.stringify({ jsonrpc: "2.0", method: 'call', params: params, id: access_id }),
            dataType:'json', type:'post', timeout:20000,
            headers:{'Content-Type':'application/json'},
            success:function(data){
                delivery_pickdone_flag = false;
                deliverymask.close();
                var dresult = data.result;
                if (!dresult.success){
                    mui.toast(dresult.message);
                    return ;
                }
                window.location.reload(true);
            },
            error:function(xhr,type,errorThrown){
                delivery_pickdone_flag = false;
                deliverymask.close();
                console.log(type);
            }
        });
    });


    //库位扫描
    document.getElementById('action_scan_location').addEventListener('tap', function(){
        wx.scanQRCode({
            needResult: 1,
            desc: '扫描库位',
            scanType: ["qrCode"],
            success: function (result) {
                var deliveryid = parseInt(document.getElementById('delivery_detail_pullrefresh').getAttribute('deliveryid'));
                var barcode = result.resultStr;
                var deliverylineidstr = deliveryid+'-0';
                mui.openWindow({'url': '/aaswechat/wms/deliverylocation/'+barcode+'/'+deliverylineidstr, 'id': 'deliverylocation'});
            },
            fail: function(result){  mui.toast(result.errMsg); }
        });
    });


});

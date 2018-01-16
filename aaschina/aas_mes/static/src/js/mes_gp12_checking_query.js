/**
 * Created by luforn on 2018-1-16.
 */

$(function(){

    function loadinglabelist(){
        var access_id = Math.floor(Math.random() * 1000 * 1000 * 1000);
        $.ajax({
            url: '/aasmes/gp12/checking/query/labelist',
            headers:{'Content-Type':'application/json'},
            type: 'post', timeout:10000, dataType: 'json',
            data: JSON.stringify({ jsonrpc: "2.0", method: 'call', params: {}, id: access_id}),
            success:function(data){
                var dresult = data.result;
                $('#checkwarning').html(dresult.message);
                if(!dresult.success){
                    layer.msg(dresult.message, {icon: 5});
                    return ;
                }
                if(dresult.labelist.length <= 0){
                    return ;
                }
                var firstlabelid = 0;
                $.each(dresult.labelist, function(index, tlabel){
                    var templi = $('<li class="aas-label"></li>').attr('labelid', tlabel.label_id).appendTo($('#gp12labelist'));
                    var tempcontent = '<a href="javascript:void(0);" style="padding:5px 15px;">'+tlabel.label_name;
                    tempcontent += '<span class="pull-right">'+tlabel.label_qty+'</span></a>';
                    templi.html(tempcontent);
                    if(index==0){
                        firstlabelid = tlabel.label_id;
                    }
                });
                loadinglabelserialnumberlist(firstlabelid);
            },
            error:function(xhr,type,errorThrown){
                scanable = true;
                console.log(type);
            }
        });
    }

    function loadinglabelserialnumberlist(labelid){
        var temparams = {'labelid': labelid};
        var access_id = Math.floor(Math.random() * 1000 * 1000 * 1000);
        $.ajax({
            url: '/aasmes/gp12/checking/query/serialist',
            headers:{'Content-Type':'application/json'},
            type: 'post', timeout:10000, dataType: 'json',
            data: JSON.stringify({ jsonrpc: "2.0", method: 'call', params: temparams, id: access_id}),
            success:function(data){
                var dresult = data.result;
                $('#serialnumberlist').html('');
                $('#checkwarning').html(dresult.message);
                if(!dresult.success){
                    layer.msg(dresult.message, {icon: 5});
                    return ;
                }
                if(dresult.serialist.length <= 0){
                    return ;
                }
                var firstserialnumberid = 0;
                $.each(dresult.serialist, function(index, tserialnumber){
                    var templi = $('<li class="aas-serialnumber"></li>').attr('serialnumberid', tserialnumber.serialnumber_id).appendTo($('#serialnumberlist'));
                    var tempcontent = '<a href="javascript:void(0);" style="padding:5px 15px;">'+tserialnumber.serialnumber_name+'</a>';
                    templi.html(tempcontent);
                    if(index==0){
                        firstserialnumberid = tserialnumber.serialnumber_id;
                    }
                });
                action_show_operationandreworklist(firstserialnumberid);
            },
            error:function(xhr,type,errorThrown){
                scanable = true;
                console.log(type);
            }
        });
    }

    function action_show_operationandreworklist(serialnumberid){
        var tparams = {'serialnumberid': serialnumberid};
        var access_id = Math.floor(Math.random() * 1000 * 1000 * 1000);
        $.ajax({
            url: '/aasmes/gp12/loadreworksandrecords',
            headers:{'Content-Type':'application/json'},
            type: 'post', timeout:30000, dataType: 'json',
            data: JSON.stringify({jsonrpc: "2.0", method: 'call', params: tparams, id: access_id}),
            success:function(data){
                var dresult = data.result;
                if(!dresult.success){
                    layer.msg(dresult.message, {icon: 5});
                    return ;
                }
                $('#meserialnumber').html(dresult.serialnumber);
                $('#operation_list').html('');
                if(dresult.operationlist.length > 0){
                    $.each(dresult.operationlist, function(index, record){
                        var lineno = index+1;
                        var operationtr = $('<tr></tr>').appendTo($('#operation_list'));
                        $('<td></td>').html(lineno).appendTo(operationtr);
                        $('<td></td>').html(record.operation_name).appendTo(operationtr);
                        $('<td></td>').html(record.operate_time).appendTo(operationtr);
                        $('<td></td>').html(record.operate_result).appendTo(operationtr);
                        $('<td></td>').html(record.scanner_name).appendTo(operationtr);
                        $('<td></td>').html(record.checker_name).appendTo(operationtr);
                        $('<td></td>').html(record.operator_name).appendTo(operationtr);
                        $('<td></td>').html(record.operate_equipment).appendTo(operationtr);
                    });
                }
                $('#rework_list').html('');
                if(dresult.reworklist.length > 0){
                    $.each(dresult.reworklist, function(index, record){
                        var lineno = index + 1;
                        var reworktr = $('<tr></tr>').appendTo($('#rework_list'));
                        $('<td></td>').html(lineno).appendTo(reworktr);
                        $('<td></td>').html(record.serialnumber).appendTo(reworktr);
                        $('<td></td>').html(record.badmode_date).appendTo(reworktr);
                        $('<td></td>').html(record.product_code).appendTo(reworktr);
                        $('<td></td>').html(record.workcenter_name).appendTo(reworktr);
                        $('<td></td>').html(record.badmode_name).appendTo(reworktr);
                        $('<td></td>').html(record.commiter_name).appendTo(reworktr);
                        $('<td></td>').html(record.state_name).appendTo(reworktr);
                        $('<td></td>').html(record.repair_result).appendTo(reworktr);
                        $('<td></td>').html(record.repair_time).appendTo(reworktr);
                        $('<td></td>').html(record.repairer_name).appendTo(reworktr);
                        $('<td></td>').html(record.ipqc_name).appendTo(reworktr);
                    });
                }
            },
            error:function(xhr,type,errorThrown){ console.log(type); }
        });
    }

    //加载当日标签
    loadinglabelist();

    //单击标签
    $('#gp12labelist').on('click', 'li.aas-label', function(){
        var labelid = parseInt($(this).attr('labelid'));
        loadinglabelserialnumberlist(labelid);
    });

    //单击序列号
    $('#serialnumberlist').on('click', 'li.aas-serialnumber', function(){
        var serialnumberid = parseInt($(this).attr('serialnumberid'));
        action_show_operationandreworklist(serialnumberid);
    });

});

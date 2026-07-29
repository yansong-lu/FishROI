#=
MuscleMosaicism.jl
Author: Michael Pan (University of Melbourne)

This script analyses the mean and variance of muscle images inside circular windows.

The main image processing function takes in a path to the image as input, as well as the pixel length and dimensions of the image (in physical units).

The outputs are:
    - A histogram of cell cross-sectional areas (*_area_hist.png)
    - An image of the ROIs (*_roi.png)
    - The borders of the ROIs, along with an outline of the region used to calculate summary statistics (*_roi_borders.png)
    - A scatter plot of the centres of each ROI, with small cells shown in red  (*_roi_centres.png)
    - A heatmap of the mean, standard deviation and coefficient of variation of a moving circular window  (*_spatial_variance.png)
    - A text file with summaries of the mean, standard deviation and coefficient of variation of the region of interest (*_area_statistics.txt)
=#

using DataFrames, CSV, Statistics, Plots, LinearAlgebra
using PyCall
py_roi = pyimport("read_roi")

function load_roi_data(image_dir,filename,pixel_length,cutoff=0.5)
    roi_data_zip = image_dir * "/" * filename * ".zip"
    roi_data_csv = image_dir * "/" * filename * ".csv"

    roi_data = DataFrame(CSV.File(roi_data_csv))
    area_cutoff = quantile(roi_data.Area,cutoff)
    roi_data.mature = roi_data.Area .> area_cutoff

    roi_coords = py_roi.read_roi_zip(roi_data_zip)
    for (name,roi) in roi_coords
        roi["x"] = roi["x"]*pixel_length
        roi["y"] = roi["y"]*pixel_length
    end

    return (roi_data,roi_coords)
end

function area_hist(roi_data,cutoff=0.5)
    area_cutoff = quantile(roi_data.Area,cutoff)
    fig = histogram(roi_data.Area, linecolor=nothing,dpi=600,label="Histogram")
    xlabel!("Area")
    ylabel!("Count")
    vline!([area_cutoff],color=:black,linewidth=2,label="Cutoff")
    return fig
end

function plot_roi_with_area(roi_data,roi_coords,dims,cutoff=true)
    fig = plot(aspect_ratio=1,dpi=600)
    for (name,roi) in roi_coords
        x = roi["x"]
        y = roi["y"]
        plot!(Shape(x,y),label="",
        c=:blue, linewidth=0)
    end
    xlims!(0,dims[1])

    #=fig = scatter(
        roi_data.XM,roi_data.YM,marker_z=roi_data.Area,label="",
        aspect_ratio=1,markersize=2,markerstrokewidth=0,markeralpha=0.8,
        c=:viridis
    )=#
    return fig
end

function plot_rois!(roi_coords;c=:black,scale=1)
    for (name,roi) in roi_coords
        x = roi["x"]*scale
        push!(x,x[1])
        y = roi["y"]*scale
        push!(y,y[1])
        plot!(x,y,label="",color=c,linewidth=10/sqrt(length(roi_coords)),linealpha=0.8)
    end
end

function plot_rois(roi_coords,dims,;c=:black,scale=1)
    fig = plot(aspect_ratio=1,dpi=600)
    plot_rois!(roi_coords;c=c,scale=scale)
    xlims!(0,dims[1])
    return fig
end

function plot_centres(roi_data,dims)
    fig = scatter(
        roi_data.XM,roi_data.YM,marker_z=roi_data.mature,label="",
        aspect_ratio=1,markersize=2,markerstrokewidth=0,markeralpha=0.8,dpi=600,
        c=cgrad([:red,:blue])
    )
    xlims!(0,dims[1])
    return fig
end

function generate_grid(roi_data,step_size)
    pad_length = 1.5*maximum(roi_data.Feret)
    x_min = minimum(roi_data.XM) - pad_length
    x_max = maximum(roi_data.XM) + pad_length
    y_min = minimum(roi_data.YM) - pad_length
    y_max = maximum(roi_data.YM) + pad_length

    X_coords = x_min:step_size:x_max
    Y_coords = y_min:step_size:y_max

    return (X_coords,Y_coords)
end

function window_analysis(roi_data,dims;step_size=5,window_radius=40)
    (X_coords,Y_coords) = generate_grid(roi_data,step_size)

    nX = length(X_coords)
    nY = length(Y_coords)
    count_matrix = zeros((nX,nY))
    mean_matrix = zeros((nX,nY))
    std_matrix = zeros((nX,nY))

    for (ix,x) in enumerate(X_coords), (iy,y) in enumerate(Y_coords)
        roi_data_window = subset(
            roi_data,
            [:XM,:YM] => ByRow((xm,ym) -> norm([xm-x,ym-y]) < window_radius)
        )
        n_cells = size(roi_data_window,1)
        count_matrix[ix,iy] = n_cells
        if n_cells < 5
            mean_area = std_area = NaN
        else
            mean_area = mean(roi_data_window.Area)
            std_area = std(roi_data_window.Area)
        end

        mean_matrix[ix,iy] = mean_area
        std_matrix[ix,iy] = std_area
    end
    return (count_matrix,mean_matrix,std_matrix)
end

function plot_count_map(roi_coords,dims,count_matrix)
    X_max = round(dims[1]) + 1
    Y_max = round(dims[2]) + 1
    X_coords = 0:step_size:X_max
    Y_coords = 0:step_size:Y_max

    fig = heatmap(X_coords,Y_coords,transpose(count_matrix),aspect_ratio=1,c=scheme,background=:black)
    plot_rois!(roi_coords,c=:white)
    xlims!(0,dims[1])
    return fig
end

function plot_spatial_analysis(roi_data,roi_coords,dims,step_size,mean_matrix,std_matrix;scheme = :viridis)
    (X_coords,Y_coords) = generate_grid(roi_data,step_size)
    
    l = @layout [a b c]
    
    p1 = heatmap(
        X_coords,Y_coords,transpose(mean_matrix),
        aspect_ratio=1,background=:black,border=:none,
        clims=(0,quantile(filter(!isnan,vec(mean_matrix)),0.95)),c=scheme,
        title="μ"
    )
    plot_rois!(roi_coords,c=:white,scale=1)
    
    p2 = heatmap(
        X_coords,Y_coords,transpose(std_matrix),
        aspect_ratio=1,background=:black,border=:none,
        clims=(0,quantile(filter(!isnan,vec(std_matrix)),0.95)),c=scheme,
        title="σ"
    )
    plot_rois!(roi_coords,c=:white,scale=1)
    
    cv_matrix = std_matrix./mean_matrix
    p3 = heatmap(
        X_coords,Y_coords,transpose(cv_matrix),
        aspect_ratio=1,background=:black,border=:none,
        clims=(0,1.1),c=scheme,
        title="σ/μ"
    )
    plot_rois!(roi_coords,c=:white,scale=1)
    
    fig = plot(p1, p2, p3, layout=l, dpi=1200, size=(1200,800))
    return fig
end

function transpose_coords!(roi_data,roi_coords)
    for (name,roi) in roi_coords
        (roi["x"],roi["y"]) = (roi["y"],roi["x"])
    end

    (roi_data.XM,roi_data.YM) = (roi_data.YM,roi_data.XM)
    (roi_data.FeretX,roi_data.FeretY) = (roi_data.FeretY,roi_data.FeretX)
    return nothing
end

function region_area_statistics(roi_data,region_summary)
    ((x1,x2),(y1,y2)) = region_summary
    roi_data_filter = subset(
        roi_data,
        :XM => ByRow(xm -> x1 < xm < x2),
        :YM => ByRow(ym -> y1 < ym < y2)
    )
    mean_region = mean(roi_data_filter.Area)
    std_region = std(roi_data_filter.Area)
    cv_region = std_region/mean_region
    return (mean_region, std_region, cv_region)
end

function process_roi_data(image_dir,filename;
    pixel_length,dims,transpose=false,region_summary=nothing)
    print("Image: $filename \n")
    (roi_data,roi_coords) = load_roi_data(image_dir,filename,pixel_length)
    if transpose
        transpose_coords!(roi_data,roi_coords)
    end

    window_radius = 3*mean(roi_data.Feret)
    step_size = window_radius/10

    print("1: Plotting ROIs\n")
    fig_area_hist = area_hist(roi_data)
    fig_roi = plot_roi_with_area(roi_data,roi_coords,dims)
    fig_roi_borders = plot_rois(roi_coords,dims,c=:black)
    fig_roi_centres = plot_centres(roi_data,dims)

    print("2: Analysing mean and variance\n")
    (count_matrix,mean_matrix,std_matrix) = window_analysis(
        roi_data,dims;step_size=step_size,window_radius=window_radius
    )
    fig_spatial = plot_spatial_analysis(roi_data,roi_coords,dims,step_size,mean_matrix,std_matrix;scheme = :viridis)

    if !isnothing(region_summary)
        (mean_region, std_region, cv_region) = region_area_statistics(roi_data,region_summary)
        # Add box of region to ROI plot
        ((x1,x2),(y1,y2)) = region_summary
        plot!(fig_roi_borders,[x1,x2,x2,x1,x1],[y1,y1,y2,y2,y1],c=:red,linewidth=1,label="")

        # Save outputs to text file
        output_file = image_dir*"/"*filename*"_area_statistics.txt"
        open(output_file,"w") do io
            write(io,"Mean: $mean_region \n")
            write(io,"Std: $std_region \n")
            write(io,"CV: $cv_region \n")
        end
    end

    if save_figures
        print("3: Saving figures\n")
        savefig(fig_area_hist,image_dir*"/"*filename*"_area_hist.png")
        savefig(fig_roi,image_dir*"/"*filename*"_roi.png")
        savefig(fig_roi_borders,image_dir*"/"*filename*"_roi_borders.png")
        savefig(fig_roi_centres,image_dir*"/"*filename*"_roi_centres.png")
        savefig(fig_spatial,image_dir*"/"*filename*"_spatial_variance.png")
    end
    return ((roi_data,roi_coords),(count_matrix,mean_matrix,std_matrix))
end

save_figures = true
##################################### Paste input code below this line ##########################




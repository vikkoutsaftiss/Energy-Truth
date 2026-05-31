using Energy_Truth.Shared.DTO_s;
using Infrastructure.DataAccess.Entities;
using Microsoft.EntityFrameworkCore;
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations.Schema;
using System.Text;

namespace Infrastructure.DataAccess.DBContext
{
    public class EnergyDbContext : DbContext
    {
        public EnergyDbContext(DbContextOptions<EnergyDbContext> options) : base(options)
        {
        }
        public DbSet<UsageData> UsageData { get; set; }
        public DbSet<ImportBatch> ImportBatches { get; set; }
        public DbSet<Building> Buildings { get; set; }
        public DbSet<Customer> Customers { get; set; }
        public DbSet<Battery> Battery { get; set; }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            modelBuilder.Ignore<CustomBatteryDTO>();

            modelBuilder.Entity<ImportBatch>()
                .Property(b => b.CustomBattery)
                .HasColumnType("jsonb");
        }

    }
}

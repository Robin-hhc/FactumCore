/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09790(unsigned int count)
{
    const unsigned int limit = 106u;
    return count > limit ? limit : count;
}

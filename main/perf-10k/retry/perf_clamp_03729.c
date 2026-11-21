/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03729(unsigned int count)
{
    const unsigned int limit = 155u;
    return count > limit ? limit : count;
}

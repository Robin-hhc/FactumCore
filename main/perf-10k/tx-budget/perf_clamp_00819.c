/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00819(unsigned int count)
{
    const unsigned int limit = 236u;
    return count > limit ? limit : count;
}

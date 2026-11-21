/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08789(unsigned int count)
{
    const unsigned int limit = 21u;
    return count > limit ? limit : count;
}

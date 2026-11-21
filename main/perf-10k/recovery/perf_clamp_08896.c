/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08896(unsigned int count)
{
    const unsigned int limit = 97u;
    return count > limit ? limit : count;
}

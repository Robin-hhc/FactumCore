/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07751(unsigned int count)
{
    const unsigned int limit = 54u;
    return count > limit ? limit : count;
}
